import os
import json
import time
import pandas as pd
import sys
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions

# 載入 .env 中的 GEMINI_API_KEY
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# 設定 API 金鑰
genai.configure(api_key=api_key)

# 建立模型
model = genai.GenerativeModel(model_name="gemini-1.5-flash")  # 確認模型名稱

# HW2 更改評分項目
ITEMS = [
    "日文檢定N1文法",
    "日文檢定N2文法",
    "日文檢定N3文法",
    "日文檢定N4文法",
    "日文檢定N5文法",
    "日文檢定N1字彙",
    "日文檢定N2字彙",
    "日文檢定N3字彙",
    "日文檢定N4字彙",
    "日文檢定N5字彙"
]

def parse_response(response_text):
    """
    嘗試解析 Gemini API 回傳的 JSON 格式結果。
    如果回傳內容被 markdown 的反引號包圍，則先移除這些標記。
    若解析失敗，則回傳所有項目皆為空的字典。
    """
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    
    try:
        result = json.loads(cleaned)
        for item in ITEMS:
            if item not in result:
                result[item] = ""
        return result
    except Exception as e:
        print(f"解析 JSON 失敗：{e}")
        print("原始回傳內容：", response_text)
        return {item: "" for item in ITEMS}

def select_dialogue_column(chunk: pd.DataFrame) -> str:
    """
    根據 CSV 欄位內容自動選取存放逐字稿的欄位。
    優先檢查常見欄位名稱："text", "utterance", "content", "dialogue"
    若都不存在，則回傳第一個欄位。
    """
    preferred = ["text", "utterance", "content", "dialogue", "Dialogue"]
    for col in preferred:
        if col in chunk.columns:
            return col
    print("CSV 欄位：", list(chunk.columns))
    return chunk.columns[0]

def process_batch_dialogue(dialogues: list, model, delimiter="-----"):
    """
    將多筆逐字稿合併成一個批次請求。
    提示中要求模型對每筆逐字稿產生 JSON 格式回覆，
    並以指定的 delimiter 分隔各筆結果。
    """
    prompt = (
        "你是一位管理與溝通分析專家，請根據以下評分項目評估主管與員工 1:1 對話中的每一句話，\n"
        + "\n".join(ITEMS) +
        "\n\n請依據評估結果，對每個項目：若主管的發言觸及該項則標記為 1，否則留空。"
        " 請對每筆逐字稿產生 JSON 格式回覆，並在各筆結果間用下列分隔線隔開：\n"
        f"{delimiter}\n"
        "例如：\n"
        "```json\n"
        "{\n  \"明確目標設定\": \"1\",\n  \"提供具體反饋\": \"\",\n  \"積極傾聽\": \"1\",\n  ...\n}\n"
        f"{delimiter}\n"
        "{{...}}\n```"
    )
    batch_text = f"\n{delimiter}\n".join(dialogues)
    content = prompt + "\n\n" + batch_text

    try:
        response = model.generate_content(content)
        print("批次 API 回傳內容：", response.text)
        parts = response.text.split(delimiter)
        results = []
        for part in parts:
            part = part.strip()
            if part:
                results.append(parse_response(part))
        if len(results) > len(dialogues):
            results = results[:len(dialogues)]
        elif len(results) < len(dialogues):
            results.extend([{item: "" for item in ITEMS}] * (len(dialogues) - len(results)))
        return results
    except exceptions.GoogleAPIError as e:
        print(f"API 呼叫失敗：{e}")
        return [{item: "" for item in ITEMS} for _ in dialogues]

def main():
    if len(sys.argv) < 2:
        print("Usage: python DRai.py <path_to_csv>")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_csv = "坂口安吾風と光と二十の私と斷句.csv"  # 修改輸出檔案名稱以反映新功能
    if os.path.exists(output_csv):
        os.remove(output_csv)
    
    df = pd.read_csv(input_csv)
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("請設定環境變數 GEMINI_API_KEY")
    
    dialogue_col = select_dialogue_column(df)
    print(f"使用欄位作為逐字稿：{dialogue_col}")
    
    batch_size = 10
    total = len(df)
    for start_idx in range(0, total, batch_size):
        end_idx = min(start_idx + batch_size, total)
        batch = df.iloc[start_idx:end_idx]
        dialogues = batch[dialogue_col].tolist()
        dialogues = [str(d).strip() for d in dialogues]
        batch_results = process_batch_dialogue(dialogues, model)
        batch_df = batch.copy()
        for item in ITEMS:
            batch_df[item] = [res.get(item, "") for res in batch_results]
        if start_idx == 0:
            batch_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
        else:
            batch_df.to_csv(output_csv, mode='a', index=False, header=False, encoding="utf-8-sig")
        print(f"已處理 {end_idx} 筆 / {total}")
        time.sleep(1)
    
    print("全部處理完成。最終結果已寫入：", output_csv)

if __name__ == "__main__":
    main()
