"""Catalogo locale fidato: split immutabili, ammissione, ritiro e flag append-only."""

import json

from .benchmark_suite import canonical
from .integrity_suite import SPLITS, duplicate, manifest, physics_fingerprint, records, reveal_proof, world_id
from .protocol import ValidationError

REASONS = ("operator_hint", "known_law", "external_disclosure", "protocol_violation")


def _exists(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


class IntegrityCatalog:
    def __init__(self, repository):
        self.repo = repository

    def import_pack(self, pack):
        public = manifest(pack)
        pid = public["pack_id"]
        with self.repo._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT private_json FROM integrity_packs WHERE id=?", (pid,)).fetchone()
            if old:
                if json.loads(old[0]) != pack:
                    raise ValidationError("Pacchetto già registrato con contenuto diverso.")
                return public  # Never reset retirement or flags on reimport.
            previous = [json.loads(row[0]) for row in db.execute("SELECT fingerprint_json FROM integrity_cases")]
            known = self.exposed_fingerprints(db)
            registered = [(row[0], physics_fingerprint(json.loads(row[1])))
                          for row in db.execute("SELECT id,record_json FROM worlds")]
            for split in SPLITS:
                for record in records(pack, split):
                    sig = physics_fingerprint(record)
                    if any(duplicate(sig, other) for other in previous) or any(duplicate(sig, other) for other in known):
                        raise ValidationError("Pacchetto duplicato o contaminato dal catalogo locale.")
                    if split == "test":
                        for existing_id, other in registered:
                            if duplicate(sig, other):
                                # A formerly untracked manifest may already have exposed an unsalted hash.
                                raise ValidationError("Caso test già registrato o accessibile tramite un mondo esistente.")
            db.execute("INSERT INTO integrity_packs VALUES(?,?,?)", (pid, canonical(public), canonical(pack)))
            for split in SPLITS:
                for record in records(pack, split):
                    wid = world_id(record)
                    db.execute("INSERT INTO integrity_cases VALUES(?,?,?,?,?,0)",
                               (wid, pid, split, canonical(record), canonical(physics_fingerprint(record))))
                    if pack["kind"] == "forge":
                        from .local_worlds import local_manifest
                        old = db.execute("SELECT record_json FROM worlds WHERE id=?", (wid,)).fetchone()
                        if old and json.loads(old[0]) != record:
                            raise ValidationError("Mondo esistente incompatibile con il pacchetto.")
                        db.execute("INSERT OR IGNORE INTO worlds VALUES(?,?,?)", (wid, canonical(record), canonical(local_manifest(record))))
        return public

    def case(self, db, wid):
        row = db.execute("SELECT c.pack_id,c.split,c.disclosed,p.manifest_json FROM integrity_cases c "
                         "JOIN integrity_packs p ON p.id=c.pack_id WHERE c.id=?", (wid,)).fetchone()
        if not row:
            return {"state": "untracked", "split": None, "manifest_hash": None, "pack_id": None, "commitment": None}
        public = json.loads(row[3])
        return {"state": "retired" if row[2] else "blind_test" if row[1] == "test" else "public_practice",
                "split": row[1], "pack_id": row[0], "manifest_hash": public["sha256"],
                "commitment": next((item["commitment"] for item in public["splits"]["test"]["commitments"] if item["world_id"] == wid), None)}

    def exposed_fingerprints(self, db):
        exposed = db.execute("SELECT w.record_json FROM worlds w WHERE "
            "json_extract(w.record_json,'$.builder_version') IS NOT NULL OR EXISTS ("
            "SELECT 1 FROM sessions s JOIN events e ON s.id=e.session_id WHERE s.world_id=w.id AND "
            "(json_extract(e.message_json,'$.type')='reveal_recorded' OR "
            "(json_extract(e.message_json,'$.type')='observation' AND NOT EXISTS "
            "(SELECT 1 FROM session_profiles sp WHERE sp.session_id=s.id AND json_extract(sp.profile_json,'$.mode')='arena'))))")
        return [physics_fingerprint(json.loads(row[0])) for row in exposed]

    def check_registration(self, db, record):
        sig = physics_fingerprint(record)
        for wid, saved in db.execute("SELECT id,fingerprint_json FROM integrity_cases WHERE split='test' AND disclosed=0"):
            if wid != world_id(record) and duplicate(sig, json.loads(saved)):
                raise ValidationError("Mondo incompatibile con la separazione del test privato.")

    def challenge_admission(self, db, record):
        wid = world_id(record)
        info = self.case(db, wid)
        if info["state"] in ("retired", "public_practice"):
            raise ValidationError("Mondo pubblico o ritirato: non ammissibile a una challenge cieca.")
        if info["state"] == "blind_test" and db.execute("SELECT 1 FROM arena_challenges WHERE world_id=?", (wid,)).fetchone():
            raise ValidationError("Il mondo test ha già una challenge; usa un nuovo caso privato.")
        signature = physics_fingerprint(record)
        if any(duplicate(signature, old) for old in self.exposed_fingerprints(db)):
            raise ValidationError("Legge già esposta nel laboratorio; challenge contaminata.")
        return info

    def session_admission(self, db, wid, profile):
        info = self.case(db, wid)
        if info["split"] == "test" and (info["state"] == "retired" or profile.get("mode") != "arena"):
            raise ValidationError("Mondo test riservato ad Arena e non riutilizzabile dopo reveal.")
        return info

    def trial_info(self, db, sid, profile):
        reasons = [row[0] for row in db.execute("SELECT reason FROM integrity_flags WHERE session_id=? ORDER BY reason", (sid,))]
        provenance = profile.get("integrity", {"state": "untracked", "split": None, "manifest_hash": None,
                                                "pack_id": None, "commitment": None})
        return {**provenance, "flags": reasons, "eligible": provenance["state"] == "blind_test" and not reasons,
                "ranking_allowed": not reasons}

    def flag(self, db, sid, reason):
        if reason not in REASONS:
            raise ValidationError("Motivo di contaminazione non valido.")
        if db.execute("SELECT 1 FROM integrity_flags WHERE session_id=? AND reason=?", (sid, reason)).fetchone():
            raise ValidationError("Flag già registrato; non è cancellabile.")
        db.execute("INSERT INTO integrity_flags VALUES(?,?)", (sid, reason))

    def authorize_reveal(self, db, wid):
        # Check all same-law aliases and unfinished investigations inside the write transaction.
        record = db.execute("SELECT record_json FROM worlds WHERE id=?", (wid,)).fetchone()
        if not record:
            return
        signature = physics_fingerprint(json.loads(record[0]))
        aliases = [row[0] for row in db.execute("SELECT id,record_json FROM worlds").fetchall()
                   if duplicate(signature, physics_fingerprint(json.loads(row[1])))]
        for alias in aliases:
            if _exists(db, "arena_challenges") and db.execute("SELECT 1 FROM arena_challenges WHERE world_id=? AND closed=0", (alias,)).fetchone():
                raise ValidationError("Reveal bloccato da una challenge ancora aperta sulla stessa legge.")
            sessions = db.execute("SELECT s.id,s.score_json FROM sessions s WHERE s.world_id=?", (alias,)).fetchall()
            for sid, score in sessions:
                terminal = db.execute("SELECT 1 FROM events WHERE session_id=? AND json_extract(message_json,'$.type')='investigation_stopped'", (sid,)).fetchone()
                if score is None and not terminal:
                    raise ValidationError("Reveal bloccato da un'indagine ancora aperta sulla stessa legge.")

    def retire(self, db, wid):
        record = db.execute("SELECT record_json FROM worlds WHERE id=?", (wid,)).fetchone()
        if not record:
            return
        sig = physics_fingerprint(json.loads(record[0]))
        for cid, saved in db.execute("SELECT id,fingerprint_json FROM integrity_cases").fetchall():
            if duplicate(sig, json.loads(saved)):
                db.execute("UPDATE integrity_cases SET disclosed=1 WHERE id=?", (cid,))

    def proof(self, db, wid):
        row = db.execute("SELECT c.split,c.disclosed,p.private_json FROM integrity_cases c "
                         "JOIN integrity_packs p ON p.id=c.pack_id WHERE c.id=?", (wid,)).fetchone()
        if not row or row[0] != "test":
            return None
        if not row[1]:
            raise ValidationError("Proof disponibile soltanto dopo reveal e ritiro.")
        return reveal_proof(json.loads(row[2]), wid)

    def public_world(self, db, value):
        info = self.case(db, value["world_id"])
        if info["split"] == "test":
            return {"world_id": value["world_id"], "experiment_budget": value["experiment_budget"], "integrity": info}
        return {**value, "integrity": info} if info["split"] is not None else value
