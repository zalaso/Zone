"""Pacchetti split v1, commitment salati e controlli finiti dei duplicati. Solo offline."""

from hashlib import sha256
import json
import math
from pathlib import Path
import re
import secrets

from .benchmark_suite import canonical, digest, make_suite, validate_suite
from .protocol import ValidationError, _invalid_constant, _unique_object, require_keys
from .simulator import acceleration_at, parse_config
from .world_ast import parse_law
from .world_forge import generate_world, validate_generated_world

VERSION = "1"
SPLITS = ("train", "development", "test")
FINGERPRINT_VERSION = "1"
DUPLICATE_TOLERANCE = 1e-6
MAX_PACK_BYTES = 8_000_000
GRID = tuple((x, y, vx, vy) for x, y in ((-7, 3), (0, 0), (8, -6), (2, 9))
             for vx, vy in ((0, 0), (3, -2), (-4, 5), (6, 7)))


def world_id(record):
    return record.get("world_id", record.get("id"))


def physics_fingerprint(record):
    config = parse_config(record["config"])
    def normalize(node):
        value = {key: item for key, item in node.items() if key != "level"}
        if "args" in value:
            value["args"] = [normalize(item) for item in value["args"]]
            if value["op"] in ("add", "mul", "norm"):
                value["args"].sort(key=canonical)
        return value
    physics = ({axis: normalize(parse_law(record["config"]["world"]["law"]).to_dict()[axis]) for axis in ("ax", "ay")}
               if config.world.family == "ast" else config.to_dict()["world"])
    values = [number for state in GRID for number in acceleration_at(config.world, state)]
    return {"version": FINGERPRINT_VERSION, "law_hash": digest(physics), "values": values}


def duplicate(left, right):
    # These values are private. Coincidence on this grid is only a conservative heuristic.
    return (left["law_hash"] == right["law_hash"] or
            math.sqrt(sum((a-b)**2 for a, b in zip(left["values"], right["values"])) / len(left["values"])) <= DUPLICATE_TOLERANCE)


def records(pack, split):
    value = pack["splits"][split]
    return value if pack["kind"] == "forge" else value["worlds"]


def commitment(record, salt):
    return digest({"domain": "zone-integrity-v1", "world_id": world_id(record), "salt": salt, "record": record})


def make_pack(seed=None, *, kind="forge", levels=(1, 2, 3, 4, 5), per_level=1, budget=3):
    seed = secrets.randbits(128) if seed is None else seed
    if type(seed) is not int or not 0 <= seed < 2**128 or kind not in ("forge", "benchmark"):
        raise ValidationError("Seed o tipo del pacchetto non valido.")
    if (not isinstance(levels, (tuple, list)) or not levels or len(set(levels)) != len(levels) or
            any(type(level) is not int or not 1 <= level <= 5 for level in levels) or
            type(per_level) is not int or not 1 <= per_level <= 5):
        raise ValidationError("Livelli o numerosità del pacchetto non validi.")
    def derived(domain):
        return int.from_bytes(sha256(f"zone-integrity:{VERSION}:{seed}:{domain}".encode()).digest()[:16], "big")
    splits, salts = {}, {}
    for split in SPLITS:
        splits[split] = ([generate_world(derived(f"{split}:{level}:{index}"), level, budget)
                          for level in levels for index in range(per_level)] if kind == "forge" else
                         make_suite(derived(split), budget))
        group = splits[split] if kind == "forge" else splits[split]["worlds"]
        if split == "test":
            salts = {world_id(record): sha256(f"zone-salt:{seed}:{world_id(record)}".encode()).hexdigest()
                     for record in group}
    pack = {"integrity_version": VERSION, "kind": kind, "generator_seed": seed,
            "splits": splits, "test_salts": salts}
    pack["sha256"] = digest(pack)
    return validate_pack(pack)


def validate_pack(pack):
    require_keys(pack, ("integrity_version", "kind", "generator_seed", "splits", "test_salts", "sha256"))
    if (pack["integrity_version"] != VERSION or pack["kind"] not in ("forge", "benchmark") or
            type(pack["generator_seed"]) is not int or not 0 <= pack["generator_seed"] < 2**128):
        raise ValidationError("Versione o tipo del pacchetto non compatibile.")
    if digest({key: value for key, value in pack.items() if key != "sha256"}) != pack["sha256"]:
        raise ValidationError("Hash del pacchetto privato non valido.")
    require_keys(pack["splits"], SPLITS)
    require_keys(pack["test_salts"], tuple(world_id(record) for record in records(pack, "test")))
    seen, fingerprints = set(), []
    for split in SPLITS:
        group = records(pack, split)
        if not isinstance(group, list) or not 1 <= len(group) <= 25:
            raise ValidationError("Numero di mondi per split non valido.")
        if pack["kind"] == "benchmark":
            validate_suite(pack["splits"][split])
        for record in group:
            if pack["kind"] == "forge":
                validate_generated_world(record)
            wid = world_id(record)
            if wid in seen:
                raise ValidationError("ID duplicato tra gli split.")
            seen.add(wid)
            signature = physics_fingerprint(record)
            if any(duplicate(signature, old) for old in fingerprints):
                raise ValidationError("Leggi duplicate o indistinguibili sulla griglia di controllo tra gli split.")
            fingerprints.append(signature)
            if split == "test" and (not isinstance(pack["test_salts"][wid], str) or
                    not re.fullmatch(r"[0-9a-f]{64}", pack["test_salts"][wid])):
                raise ValidationError("Nonce del commitment non valido.")
    return pack


def manifest(pack):
    # Callers validate the private pack once at their trust boundary.
    value = {"integrity_version": VERSION, "pack_id": "i" + pack["sha256"][:16], "kind": pack["kind"],
             "fingerprint_version": FINGERPRINT_VERSION, "splits": {
                 split: ({"count": len(records(pack, split)), "dataset_hash": digest(pack["splits"][split]),
                          "world_ids": [world_id(record) for record in records(pack, split)]} if split != "test" else
                         {"count": len(records(pack, split)), "commitments": [{"world_id": world_id(record),
                          "commitment": commitment(record, pack["test_salts"][world_id(record)])}
                          for record in records(pack, split)]}) for split in SPLITS}}
    value["sha256"] = digest(value)
    return value


def reveal_proof(pack, wid):
    matching = [record for record in records(pack, "test") if world_id(record) == wid]
    if len(matching) != 1:
        raise ValidationError("Mondo test assente dal pacchetto.")
    public = manifest(pack)
    return {"integrity_version": VERSION, "manifest_hash": public["sha256"], "world_id": wid,
            "record_json": canonical(matching[0]), "salt": pack["test_salts"][wid]}


def verify_reveal(public, proof, expected_hash=None):
    require_keys(public, ("integrity_version", "pack_id", "kind", "fingerprint_version", "splits", "sha256"))
    require_keys(proof, ("integrity_version", "manifest_hash", "world_id", "record_json", "salt"))
    calculated = digest({key: value for key, value in public.items() if key != "sha256"})
    if (public["integrity_version"] != VERSION or proof["integrity_version"] != VERSION or
            calculated != public["sha256"] or proof["manifest_hash"] != calculated or
            expected_hash is not None and expected_hash != calculated):
        raise ValidationError("Manifest originale o versione del reveal non corrispondente.")
    expected = [item["commitment"] for item in public["splits"]["test"]["commitments"] if item["world_id"] == proof["world_id"]]
    try:
        record = json.loads(proof["record_json"], object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, TypeError, RecursionError):
        raise ValidationError("Record canonico del reveal non valido.") from None
    if (not isinstance(record, dict) or canonical(record) != proof["record_json"] or
            len(expected) != 1 or world_id(record) != proof["world_id"] or
            commitment(record, proof["salt"]) != expected[0]):
        raise ValidationError("Reveal non coerente con il commitment originale.")
    return True


def read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_PACK_BYTES + 1)
    if len(raw) > MAX_PACK_BYTES:
        raise ValidationError("File integrità troppo grande.")
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ValidationError("File JSON integrità non valido.") from None


def read_pack(path):
    try:
        return validate_pack(read_json(path))
    except (KeyError, TypeError, AttributeError):
        raise ValidationError("Struttura del pacchetto non valida.") from None


def benchmark_binding(pack, suite, wid):
    if pack["kind"] != "benchmark":
        raise ValidationError("Il benchmark richiede un pacchetto benchmark.")
    matching = [split for split in SPLITS if pack["splits"][split] == suite and
                any(world_id(record) == wid for record in records(pack, split))]
    if len(matching) != 1:
        raise ValidationError("Suite o mondo non corrispondenti agli split impegnati.")
    split = matching[0]
    public = manifest(pack)
    return {"integrity_version": VERSION, "pack_id": public["pack_id"], "manifest_hash": public["sha256"],
            "split": split, "commitment": next((item["commitment"] for item in public["splits"]["test"]["commitments"]
                if item["world_id"] == wid), None), "scope": "blind_test" if split == "test" else "public_practice"}
