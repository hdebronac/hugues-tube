"""Reprise des lots Claude entre deux passages, sans double envoi."""

import json
import sys
from datetime import date
from types import SimpleNamespace as NS

import tube.classement as cl
from tube.commun import Interet

INTERET = Interet(id="t", titre="T", description="", demi_vie_mois=12, depuis=date(2020, 1, 1),
                  mots_cles=("x",), consigne_classement="")
EL = {"id": "42", "auteur": "a", "date": 0, "fil": "1", "titre_fil": None, "texte": "voir",
      "videos": ["AAAAAAAAAAA"], "mots": ["x"], "type": "commentaire"}


class FauxLots:
    def __init__(self):
        self.crees, self.termine = [], False

    def create(self, requests):
        self.crees.append(requests)
        return NS(id="lot_1")

    def retrieve(self, lot_id):
        return NS(processing_status="ended" if self.termine else "in_progress")

    def results(self, lot_id):
        texte = json.dumps({"videos": [{"id": "AAAAAAAAAAA", "verdict": "recommande",
                                        "type_contenu": "technique"}]})
        message = NS(stop_reason="end_turn", content=[NS(type="text", text=texte)])
        yield NS(custom_id="m0", result=NS(type="succeeded", message=message))


def test_lot_interrompu_repris_sans_renvoi(tmp_path, monkeypatch):
    lots = FauxLots()
    client = NS(messages=NS(batches=lots))
    monkeypatch.setitem(sys.modules, "anthropic", NS(Anthropic=lambda **_: client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "factice")
    monkeypatch.setattr(cl, "CHEMIN", tmp_path / "classements.json")
    monkeypatch.setattr(cl, "CHEMIN_LOTS", tmp_path / "lots.json")
    monkeypatch.setattr(cl, "ATTENTE_MAX", 0)
    monkeypatch.setattr(cl, "SEUIL_DIRECT", 0)  # force le passage par l'API Batch

    # Premier passage : le lot ne finit pas à temps, il est seulement enregistré.
    assert cl.classer([(INTERET, EL)], {}) == {}
    assert len(lots.crees) == 1
    assert json.loads((tmp_path / "lots.json").read_text()) == {"lot_1": {"m0": "t:42"}}

    # Second passage : le lot est terminé, on le récupère sans en créer un nouveau.
    lots.termine = True
    cache = cl.classer([(INTERET, EL)], {})
    assert len(lots.crees) == 1
    assert cache["t:42"]["AAAAAAAAAAA"]["verdict"] == "recommande"
    assert json.loads((tmp_path / "lots.json").read_text()) == {}


def test_appels_directs_sous_le_seuil(tmp_path, monkeypatch):
    texte = json.dumps({"videos": [{"id": "AAAAAAAAAAA", "verdict": "critique",
                                    "type_contenu": "vlog"}]})
    appels = []

    def create(**params):
        appels.append(params)
        if "panne" in params["messages"][0]["content"]:
            raise RuntimeError("erreur réseau simulée")
        return NS(stop_reason="end_turn", content=[NS(type="text", text=texte)])

    client = NS(messages=NS(create=create, batches=FauxLots()))
    monkeypatch.setitem(sys.modules, "anthropic", NS(Anthropic=lambda **_: client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "factice")
    monkeypatch.setattr(cl, "CHEMIN", tmp_path / "classements.json")
    monkeypatch.setattr(cl, "CHEMIN_LOTS", tmp_path / "lots.json")
    en_panne = {**EL, "id": "43", "texte": "panne"}

    cache = cl.classer([(INTERET, EL), (INTERET, en_panne)], {})
    assert len(appels) == 2 and client.messages.batches.crees == []
    assert cache["t:42"]["AAAAAAAAAAA"]["verdict"] == "critique"
    assert "t:43" not in cache  # l'échec n'invente pas de verdict : retenté au prochain passage
