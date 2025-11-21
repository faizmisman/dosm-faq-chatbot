from app.llm_rag.rag_pipeline import answer_query
import os

def test_rag_refusal_without_dataset():
    os.environ.pop("DATASET_PATH", None)
    rr = answer_query("What is CPI 2023?")
    assert rr.failure_mode is not None
    assert rr.confidence == 0.0

def test_rag_answer_with_dataset(tmp_path):
    # create minimal dataset CSV
    p = tmp_path / "data.csv"
    p.write_text("year,value\n2023,123\n2024,130\n")
    os.environ["DATASET_PATH"] = str(p)
    rr = answer_query("2023 123")
    assert rr.failure_mode is None
    assert rr.confidence > 0.0
    assert rr.citations
