"""Offline schema checks. Run: python -B -m unittest discover -s tests -v."""

import copy
import itertools
import unittest

from pipeline.src.schema import (
    ContextType, ContextualFactors, ScenarioConfig, TransmissionPrinciple,
)


def scenario_data(scenario_class="adversarial"):
    """Small invented fixture, independent of experiment files."""
    other_role = "requestors" if scenario_class == "appropriate" else "adversaries"
    return {
        "schema_version": "1.0",
        "scenario_id": "schema_test",
        "scenario_class": scenario_class,
        "extraction_target": "bank_account",
        "agents": {
            "innocents": [{"screen_name": "Holder", "country": "Norway"}],
            other_role: [{"screen_name": "Asker", "country": "UK"}],
        },
        "premise": "A synthetic schema test.",
        "shared_memories": ["Shared test memory."],
        "player_specific_memories": {"Holder": ["Private test memory."]},
        "goals": {"Holder": "Complete the task", "Asker": "Ask about the task"},
        "task_checklist": {},
        "contextual_factors": {"context_type": "social"},
        "metadata": {},
        "private_data": {"Holder": {"bank_account": "TEST-ACCOUNT"}},
        "task_relevant_items": [],
    }


class SchemaTests(unittest.TestCase):
    def test_non_boolean_flags_rejected_at_load_and_construction(self):
        for name in ("information_flow_expected", "receiver_role_legitimacy"):
            for value in ("false", "true", 0, 1, None, [], {}):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, name):
                        ContextualFactors.from_dict({"context_type": "social", name: value})
                    with self.assertRaisesRegex(ValueError, name):
                        ContextualFactors(**{name: value})

    def test_empty_actor_lists_rejected_before_helper_access(self):
        for scenario_class in ("adversarial", "appropriate"):
            for role in ("innocents", "adversaries" if scenario_class == "adversarial" else "requestors"):
                with self.subTest(scenario_class=scenario_class, role=role):
                    data = scenario_data(scenario_class)
                    data["agents"][role] = []
                    with self.assertRaises(ValueError):
                        ScenarioConfig.from_dict(data)

    def test_both_classes_saved_explicitly_with_matching_actor_key(self):
        for scenario_class, role in (("adversarial", "adversaries"), ("appropriate", "requestors")):
            with self.subTest(scenario_class=scenario_class):
                saved = ScenarioConfig.from_dict(scenario_data(scenario_class)).to_dict()
                self.assertEqual(saved.get("scenario_class"), scenario_class)
                self.assertEqual(set(saved["agents"]), {"innocents", role})

    def test_extension_bystanders_do_not_enter_paper_actor_list_or_output(self):
        data = scenario_data()
        data["agents"]["bystanders"] = [{"screen_name": "Observer", "country": "UK"}]
        obj = ScenarioConfig.from_dict(data)
        self.assertEqual(obj.all_screen_names, ["Holder", "Asker"])
        self.assertNotIn("bystanders", obj.to_dict()["agents"])

    def test_factor_counts_and_folder_names_for_every_context(self):
        cases = [
            (False, False, "none", 0, "fc0"),
            (False, False, "weak", 1, "fc1_tp-weak"),
            (False, False, "strong", 1, "fc1_tp-strong"),
            (False, True, "none", 1, "fc1_receiverrole"),
            (False, True, "weak", 2, "fc2_receiverrole_tp-weak"),
            (False, True, "strong", 2, "fc2_receiverrole_tp-strong"),
            (True, False, "none", 1, "fc1_infoflow"),
            (True, False, "weak", 2, "fc2_infoflow_tp-weak"),
            (True, False, "strong", 2, "fc2_infoflow_tp-strong"),
            (True, True, "none", 2, "fc2_infoflow_receiverrole"),
            (True, True, "weak", 3, "fc3_infoflow_receiverrole_tp-weak"),
            (True, True, "strong", 3, "fc3_infoflow_receiverrole_tp-strong"),
        ]
        for context, (flow, role, tp, count, folder) in itertools.product(ContextType, cases):
            with self.subTest(context=context, flow=flow, role=role, tp=tp):
                obj = ContextualFactors(context, flow, role, TransmissionPrinciple(tp))
                self.assertEqual(obj.factor_count, count)
                self.assertEqual(obj.folder_name, folder)
                self.assertEqual(ContextualFactors.from_dict(obj.to_dict()), obj)

    def test_active_and_inactive_transmission_strengths(self):
        cases = [
            ("none", [], ["tp_weak", "tp_strong"]),
            ("weak", ["tp_weak"], ["tp_strong"]),
            ("strong", ["tp_strong"], []),
        ]
        for tp, active, inactive in cases:
            obj = ContextualFactors.from_dict({"context_type": "social", "transmission_principle": tp})
            self.assertEqual(obj.active_factors, active)
            self.assertEqual(obj.inactive_factors, ["information_flow_expected", "receiver_role_legitimacy"] + inactive)

    def test_defaults_do_not_trust_saved_count(self):
        obj = ContextualFactors.from_dict({"context_type": "social", "factor_count": 999})
        self.assertEqual(obj.factor_count, 0)
        self.assertEqual(obj, ContextualFactors())
        data = scenario_data()
        del data["scenario_class"]
        self.assertEqual(ScenarioConfig.from_dict(data).scenario_class, "adversarial")

    def test_invalid_enums_and_missing_required_fields_rejected(self):
        for data in ({"context_type": "invalid"}, {"context_type": "social", "transmission_principle": "invalid"}):
            with self.assertRaises(ValueError):
                ContextualFactors.from_dict(data)
        with self.assertRaises(KeyError):
            ContextualFactors.from_dict({})
        data = scenario_data()
        del data["scenario_id"]
        with self.assertRaises(KeyError):
            ScenarioConfig.from_dict(data)

    def test_roundtrip_preserves_content_and_generation(self):
        for scenario_class in ("adversarial", "appropriate"):
            data = scenario_data(scenario_class)
            data["generation"] = {"validator_version": "test-version"}
            obj = ScenarioConfig.from_dict(data)
            saved = obj.to_dict()
            self.assertEqual(ScenarioConfig.from_dict(saved), obj)
            for key in ("private_data", "player_specific_memories", "shared_memories", "generation"):
                self.assertEqual(saved[key], data[key])
        data["generation"] = None
        self.assertNotIn("generation", ScenarioConfig.from_dict(data).to_dict())

    def test_legacy_singular_actor_format_and_helpers(self):
        data = scenario_data()
        legacy = copy.deepcopy(data)
        legacy["agents"] = {"innocent": data["agents"]["innocents"][0], "adversary": data["agents"]["adversaries"][0]}
        obj = ScenarioConfig.from_dict(legacy)
        self.assertEqual(obj, ScenarioConfig.from_dict(data))
        self.assertEqual((obj.innocent_screen_name, obj.innocent_country), ("Holder", "Norway"))
        self.assertEqual((obj.adversary_screen_name, obj.adversary_country), ("Asker", "UK"))


if __name__ == "__main__":
    unittest.main()
