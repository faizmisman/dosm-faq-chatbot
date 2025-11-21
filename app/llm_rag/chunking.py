import pandas as pd
from typing import List, Dict, Any

def load_dataset(path: str) -> pd.DataFrame:
	return pd.read_csv(path)

def build_chunks(df: pd.DataFrame, chunk_size: int = 25) -> List[Dict[str, Any]]:
	chunks: List[Dict[str, Any]] = []
	total = len(df)
	for start in range(0, total, chunk_size):
		end = min(start + chunk_size, total)
		slice_df = df.iloc[start:end]
		text_parts = []
		for idx, row in slice_df.iterrows():
			text_parts.append(" ".join([f"{col}={row[col]}" for col in df.columns]))
		content = "\n".join(text_parts)
		chunks.append({
			"id": f"chunk_{start}_{end}",
			"content": content,
			"start_row": start,
			"end_row": end - 1
		})
	return chunks
