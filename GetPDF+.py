import os
import json
import time
import pandas as pd
import sys
import re
from itertools import chain
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
print(os.path.exists('NotoSansJP-Regular.ttf'))  # True 表示找到了


pdfmetrics.registerFont(TTFont('NotoSansJP', 'NotoSansJP-VariableFont_wght.ttf'))


# 載入 .env 中的 GEMINI_API_KEY
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# 建立模型
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

# 評分項目（僅字彙）
ITEMS = [
    "日文檢定N1字彙",
    "日文檢定N2字彙",
    "日文檢定N3字彙",
    "日文檢定N4字彙",
    "日文檢定N5字彙"
]

def parse_response(response_text):
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
                result[item] = []
        return result
    except Exception as e:
        print(f"解析 JSON 失敗：{e}")
        print("原始回傳內容：", response_text)
        return {item: [] for item in ITEMS}

def select_dialogue_column(chunk: pd.DataFrame) -> str:
    preferred = ["text", "utterance", "content", "dialogue", "Dialogue"]
    for col in preferred:
        if col in chunk.columns:
            return col
    print("CSV 欄位：", list(chunk.columns))
    return chunk.columns[0]

def extract_japanese_words(text):
    return re.findall(r'[\u3040-\u30FF\u4E00-\u9FFF]+', text)

def get_unmatched_words(text, matched_words):
    words = extract_japanese_words(text)
    return [w for w in words if w not in matched_words]

def process_batch_dialogue(dialogues: list, model, delimiter="-----"):
    prompt = (
        "あなたは日本語教師であり、学生が日本語能力試験（JLPT）の語彙と文法レベルを理解するためのサポートをしています。\n"
        "以下は学生の文章または逐語記録です。\n"
        + "\n".join(ITEMS) +
        "\n\n各文に対して、含まれている語彙項目のレベルを評価し、それぞれのレベルで見つかった単語をリストで返してください。\n"
        "出力形式はJSONとし、各項目に対して単語リストを出力してください。\n"
        "文と文の間は '-----' で区切ってください。\n"
        "例：\n"
        "```json\n"
        "{\n"
        "  \"日文檢定N1字彙\": [\"哲学\", \"抽象\"],\n"
        "  \"日文檢定N2字彙\": [],\n"
        "  \"日文檢定N3字彙\": [\"光\", \"変化\"],\n"
        "  \"日文檢定N4字彙\": [],\n"
        "  \"日文檢定N5字彙\": [\"私\", \"風\"]\n"
        "}\n"
        "```\n"
    )
    batch_text = f"\n-----\n".join(dialogues)
    content = prompt + "\n\n" + batch_text

    try:
        response = model.generate_content(content)
        print("批次 API 回傳內容：", response.text)
        parts = response.text.split("-----")
        results = []
        for part in parts:
            part = part.strip()
            if part:
                results.append(parse_response(part))
        if len(results) > len(dialogues):
            results = results[:len(dialogues)]
        elif len(results) < len(dialogues):
            results.extend([{item: [] for item in ITEMS}] * (len(dialogues) - len(results)))
        return results
    except exceptions.GoogleAPIError as e:
        print(f"API 呼叫失敗：{e}")
        return [{item: [] for item in ITEMS} for _ in dialogues]

def generate_pdf_report(sentences_info, output_path):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("NotoSansJP", 11)

    for idx, info in enumerate(sentences_info):
        c.drawString(50, y, f"【第 {idx+1} 句】 {info['sentence']}")
        y -= 20
        for level in ITEMS:
            words = info['matched'].get(level, [])
            c.drawString(60, y, f"{level}: {'、'.join(words) if words else '（なし）'}")
            y -= 18
        unmatched = info['unmatched']
        c.drawString(60, y, f"未分類詞彙: {'、'.join(unmatched) if unmatched else '（なし）'}")
        y -= 30
        if y < 100:
            c.showPage()
            y = height - 50
            c.setFont("NotoSansJP", 11)

    c.save()

def main():
    if len(sys.argv) < 2:
        print("Usage: python DRai.py <path_to_csv>")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = "坂口安吾風と光と二十の私と斷句.csv"
    summary_csv = "統計結果_summary.csv"
    pdf_report = "詞彙等級報告.pdf"

    if os.path.exists(output_csv):
        os.remove(output_csv)
    if os.path.exists(summary_csv):
        os.remove(summary_csv)
    if os.path.exists(pdf_report):
        os.remove(pdf_report)

    df = pd.read_csv(input_csv)
    if not api_key:
        raise ValueError("請設定環境變數 GEMINI_API_KEY")

    dialogue_col = select_dialogue_column(df)
    print(f"使用欄位作為逐字稿：{dialogue_col}")

    batch_size = 10
    total = len(df)
    total_counts = {item: 0 for item in ITEMS}
    sentences_info = []

    for start_idx in range(0, total, batch_size):
        end_idx = min(start_idx + batch_size, total)
        batch = df.iloc[start_idx:end_idx]
        dialogues = batch[dialogue_col].astype(str).str.strip().tolist()
        batch_results = process_batch_dialogue(dialogues, model)
        batch_df = batch.copy()

        # 將結果寫入 batch_df 並彙整 PDF 所需資料
        for i, result in enumerate(batch_results):
            sentence = dialogues[i]
            matched = {
                item: result.get(item, []) if isinstance(result.get(item, []), list) else []
                for item in ITEMS
            }
            matched_words = list(chain.from_iterable(matched.values()))
            unmatched = get_unmatched_words(sentence, matched_words)

            # 統計計數
            for item in ITEMS:
                total_counts[item] += len(matched[item])

            sentences_info.append({
                "sentence": sentence,
                "matched": matched,
                "unmatched": unmatched
            })

        for item in ITEMS:
            batch_df[item] = [", ".join(result.get(item, [])) for result in batch_results]

        if start_idx == 0:
            batch_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
        else:
            batch_df.to_csv(output_csv, mode='a', index=False, header=False, encoding="utf-8-sig")

        print(f"已處理 {end_idx} 筆 / {total}")
        time.sleep(1)

    pd.DataFrame([total_counts]).to_csv(summary_csv, index=False, encoding="utf-8-sig")
    generate_pdf_report(sentences_info, pdf_report)

    print("全部處理完成。最終結果已寫入：", output_csv)
    print("統計結果已寫入：", summary_csv)
    print("PDF 報告已產出：", pdf_report)

if __name__ == "__main__":
    main()
