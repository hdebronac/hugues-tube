from types import SimpleNamespace as NS

from tube.classement import _lire_reponse


def msg(texte, stop="end_turn"):
    return NS(stop_reason=stop, content=[NS(type="text", text=texte)])


def test_reponse_valide_filtree_sur_les_ids_attendus():
    m = msg('{"videos":[{"id":"AAAAAAAAAAA","verdict":"recommande","type_contenu":"technique"},'
            '{"id":"INVENTEEEEE","verdict":"recommande","type_contenu":"vlog"}]}')
    assert _lire_reponse(m, ["AAAAAAAAAAA"]) == {"AAAAAAAAAAA": {"verdict": "recommande",
                                                                 "type_contenu": "technique"}}


def test_refus_ou_troncature_ne_produisent_pas_de_verdict():
    assert _lire_reponse(msg("", stop="refusal"), ["AAAAAAAAAAA"]) is None
    assert _lire_reponse(msg('{"videos":[', stop="max_tokens"), ["AAAAAAAAAAA"]) is None
    assert _lire_reponse(msg("pas du json"), ["AAAAAAAAAAA"]) is None
