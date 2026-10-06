import pytest
from pydantic import ValidationError
from pain_radar.ai.schemas import PainSignalSchema, OpportunitySynthesisSchema


def test_pain_signal_schema_valid():
    data = {
        "is_real_problem": True,
        "pain_level": 4,
        "recurring_problem": True,
        "manual_workaround": True,
        "existing_solution_failure": False,
        "purchase_signal": True,
        "switching_signal": False,
        "problem_type": "manual_work",
        "problem_statement": "Small businesses manually reconcile invoices and payments across banking and accounting tools.",
        "target_user": "Small business bookkeepers",
        "current_workaround": "Excel spreadsheets",
        "why_painful": "Wastes 3 hours every Friday.",
        "confidence": 0.95
    }
    schema = PainSignalSchema.model_validate(data)
    assert schema.is_real_problem is True
    assert schema.pain_level == 4
    assert schema.confidence == 0.95


def test_pain_signal_rejects_generic_statements():
    bad_examples = [
        "Users struggle with manual work.",
        "SaaS founders have difficulty with marketing.",
        "Businesses face operational overhead.",
        "Businesses struggle with invoicing.",
        "Founders struggle with marketing.",
        "Too short statement",
    ]
    base_data = {
        "is_real_problem": True,
        "pain_level": 4,
        "recurring_problem": True,
        "manual_workaround": True,
        "existing_solution_failure": False,
        "purchase_signal": False,
        "switching_signal": False,
        "problem_type": "manual_work",
        "target_user": "SMBs",
        "current_workaround": "Excel",
        "why_painful": "Takes hours",
        "confidence": 0.90,
    }
    for bad in bad_examples:
        data = {**base_data, "problem_statement": bad}
        with pytest.raises(ValidationError):
            PainSignalSchema.model_validate(data)


def test_pain_signal_clamping():
    data = {
        "is_real_problem": True,
        "pain_level": 10,  # Should clamp to 5
        "recurring_problem": True,
        "manual_workaround": True,
        "existing_solution_failure": False,
        "purchase_signal": False,
        "switching_signal": False,
        "problem_type": "manual_work",
        "problem_statement": "Early-stage SaaS founders manually combine prospect research, email discovery, personalization and Gmail to run cold outreach.",
        "target_user": "Small business",
        "current_workaround": "Excel",
        "why_painful": "Wastes time",
        "confidence": 1.5  # Should clamp to 1.0
    }
    schema = PainSignalSchema.model_validate(data)
    assert schema.pain_level == 5
    assert schema.confidence == 1.0


def test_pain_signal_missing_field():
    data = {
        "is_real_problem": True,
        # missing pain_level
        "recurring_problem": True,
    }
    with pytest.raises(ValidationError):
        PainSignalSchema.model_validate(data)


def test_opportunity_synthesis_schema():
    data = {
        "problem_summary": "Web development agencies manually chase client approvals across scattered WhatsApp and email threads because current portals lack external sign-off links.",
        "target_user": "Digital agencies",
        "why_it_hurts": "Blocks sprints and causes revenue delays.",
        "current_workaround": "WhatsApp threads and email followups.",
        "existing_solutions": ["Asana", "Email"],
        "observed_gaps": ["No external client sign-off link."],
        "product_direction": "A single-click client review portal.",
        "risks": ["Client adoption resistance."]
    }
    schema = OpportunitySynthesisSchema.model_validate(data)
    assert schema.target_user == "Digital agencies"
    assert len(schema.existing_solutions) == 2


def test_opportunity_synthesis_rejects_generic():
    data = {
        "problem_summary": "Businesses struggle with invoicing.",
        "target_user": "Digital agencies",
        "why_it_hurts": "Blocks sprints and causes revenue delays.",
        "current_workaround": "WhatsApp threads and email followups.",
        "existing_solutions": ["Asana", "Email"],
        "observed_gaps": ["No external client sign-off link."],
        "product_direction": "A single-click client review portal.",
        "risks": ["Client adoption resistance."]
    }
    with pytest.raises(ValidationError):
        OpportunitySynthesisSchema.model_validate(data)

