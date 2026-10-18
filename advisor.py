"""Local Japanese manufacturing method selector using Laya (no hosted API)."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / "models"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

METHODS = {
    "effects": {
        "name": "要因効果分析",
        "criterion": "何が効くか、影響の大きい因子の特定・絞り込み。主効果や交互作用を調べる。",
        "reason": "まず条件ごとの効き方を調べ、優先して調整する因子を絞り込む方法です。",
        "next": "候補因子と変えられる範囲を整理し、組み合わせの影響も推定できる計画実験を検討します。",
        "limit": "主効果が大きいだけで原因や最適条件は確定しません。履歴データだけの場合は偏りの確認が必要です。",
        "check": "調べたい因子、試験範囲、測定の再現性は分かっていますか？",
    },
    "surface": {
        "name": "応答曲面法",
        "criterion": "絞った連続パラメーターの関係を近似し、良い条件や合格範囲・プロセスウィンドウを明確化する。",
        "reason": "条件と品質の関係を地図のように近似し、良い条件や許容範囲を把握する方法です。",
        "next": "主要な連続因子と範囲を絞り、計画実験で近似式を作り、合格境界と候補条件を別試験で確認します。",
        "limit": "なめらかな局所近似が前提です。急な現象変化や複雑な山谷、範囲外の予測には向きません。",
        "check": "主要因子は絞られていますか？ 数値で連続的に変えられ、まとまった試験ができますか？",
    },
    "sequential": {
        "name": "逐次最適化",
        "criterion": "結果を見て次の実験を選ぶ条件探索。高価な試験・CAE、少ない試行、過去の知見を使う最適化。",
        "reason": "試した結果で見通しを更新し、次に試す条件を選び直す方法です。過去の知見も初期モデルに使えます。",
        "next": "目的値・制約・試験可能範囲を決め、既存データの適用範囲を点検し、少数の初期試験から段階的に探索します。",
        "limit": "結果を待って次の条件を決められることが前提です。過去製品からの知見の転用効果や真の最適解は保証されません。",
        "check": "1条件の費用・時間と、結果を見て次の試験条件を変えられるかを確認してください。",
    },
    "online": {
        "name": "オンライン学習",
        "criterion": "新しい実績データで予測モデルを継続更新。材料ロット・工具摩耗・環境の変化へ追従し続ける。",
        "reason": "稼働中に届く結果を使い、予測モデルを継続的に更新する方法です。",
        "next": "予測してから実測で評価する運用を作り、結果の遅れ・変化の速さ・古いデータの扱いを確認します。",
        "limit": "過去データの活用だけでは選ぶ根拠になりません。予測モデルの更新だけで運転条件は最適化されません。",
        "check": "継続更新が必要ですか？ 品質結果は変化に追従できる速さで届きますか？",
    },
}

EXAMPLES = [
    "影響度の大きいパラメーターを特定したい。温度、圧力、速度のどれが反りに効くかを調べたい。",
    "プロセスウィンドウを明確化したい。主要因子は温度と圧力に絞れており、合格する連続条件の範囲を近似式で説明したい。",
    "製品設計パラメーターを探索したい。CAEに1回8時間かかるので、結果を見て次の条件を選び、少ない試行で軽量化したい。",
    "加工プロセスパラメーターを探索したい。試験は高価なので、測定結果を見ながら次の切削条件を決めたい。",
    "過去の知見を活用しつつ対象製品のパラメーターを最適化したい。過去製品のデータを初期モデルに使い、新しい実験結果から次の条件を決めたい。",
    "工具摩耗と材料ロットの変化に追従したい。加工ごとに届く品質実績で予測モデルを継続更新したい。",
    "製品設計パラメーターを探索したい。",
]


def explicit_purpose(state: str):
    """Conservative, inspectable domain rules; do not interpret a denied goal as intent.

    Laya still evaluates every request. These rules protect common explicit business
    goals where the general checkpoint's direct classification is unreliable.
    """
    clauses = re.split(r"[。！？\n]|[、,](?=.*(?:不要|しない|必要ない))", state)
    positive = "。".join(s for s in clauses if not re.search(r"不要|しない|必要ない|せず|望まない", s))
    if re.search(r"(?:継続|逐次|随時|リアルタイム|毎時|加工ごと).{0,35}(?:更新|学習)|(?:予測モデル|モデル).{0,20}(?:更新|学習)", positive) and re.search(r"追従|変化|摩耗|継続|逐次|随時|毎時|加工ごと", positive):
        return "online", "継続的なモデル更新の明示目的"
    if re.search(r"(?:影響|効果|効く|寄与).{0,35}(?:特定|絞|理解|調べ|知り)|(?:どの|何が).{0,20}(?:効|影響)|因子.{0,20}絞り込", positive):
        return "effects", "影響因子の把握・絞り込みの明示目的"
    if re.search(r"プロセスウィンドウ|合格.{0,15}(?:範囲|領域)|公差.{0,15}(?:範囲|領域)|二次式|近似式|応答.{0,10}近似", positive):
        return "surface", "条件と品質の関係・合格範囲の明示目的"
    if re.search(r"(?:結果|測定).{0,35}(?:次|選び直)|次.{0,15}(?:試験|実験|条件|設計点)|(?:少ない|少数|高価).{0,20}(?:試行|試験|実験)|試験.{0,15}(?:少しずつ|段階)", positive):
        return "sequential", "結果を見て次の条件を決める明示目的"
    return None, None


class Advisor:
    def __init__(self):
        self.agent = None

    def load(self):
        if self.agent is None:
            revision_file = ROOT / "model_revision.txt"
            if not revision_file.exists():
                raise RuntimeError("モデルが未取得です。アプリのフォルダーにある setup.cmd を実行してください。")
            revision = revision_file.read_text(encoding="utf-8").strip()
            model = ROOT / "models/hub/models--convaiinnovations--laya/snapshots" / revision / "multilingual"
            if not (model / "model.safetensors").is_file():
                raise RuntimeError("保存済みモデルが見つかりません。.venv\\Scripts\\python.exe download_model.py を実行して取得してください。")
            import torch
            import laya
            torch.set_num_threads(min(4, os.cpu_count() or 1))
            self.agent = laya.load(str(model), device="cpu")
        return self.agent

    def recommend(self, text: str, context: str = "") -> dict:
        text = text.strip()
        if not text:
            raise ValueError("やりたいことを入力してください。")
        if len(text) + len(context) > 1600:
            raise ValueError("入力は補足を含め1600文字以内にしてください。")
        state = text + ("\n補足条件：" + context if context else "")
        agent = self.load()
        # Leave enough space for all Japanese option descriptions and the entire state.
        if len(agent.tok.encode(state)) > 1800:
            raise ValueError("入力のトークン数が多いため短くしてください。")
        first = agent.predict(state, {"method": {
            "type": "choice",
            "instructions": "製造業の相談に対し、最初に使う手法を目的と制約から1つ選ぶ。過去知見の利用だけならオンライン学習とはしない。",
            "criteria": {key: info["name"] + "：" + info["criterion"] for key, info in METHODS.items()},
        }, "window": {
            "type": "noul", "instructions": "合格する条件の範囲・プロセスウィンドウを明確化したい相談ですか？",
        }, "update": {
            "type": "noul", "instructions": "新しい品質実績で予測モデルを継続更新し、工具摩耗や材料の変化に追従したい相談ですか？",
        }}, max_len=4096, head_max_len=640)["answers"]
        choice = first["method"]
        key = choice["choice"]
        basis = "Layaの4択判定"
        # Explicit domain policy using Laya intent predictions. These thresholds are
        # provisional engineering settings, not calibrated manufacturing probabilities.
        if first["update"]["noul"] >= .90:
            key = "online"
            basis = "Layaの継続更新の目的判定＋適用目的の優先規則"
        elif first["window"]["noul"] >= .90:
            key = "surface"
            basis = "Layaの合格範囲の目的判定＋適用目的の優先規則"
        purpose, purpose_reason = explicit_purpose(state)
        if purpose:
            key = purpose
            basis = "Laya＋製造業の目的優先ルール：" + purpose_reason
        if key not in METHODS:
            raise RuntimeError("モデルが未定義の手法を返しました。")
        method = METHODS[key]
        suitability = agent.predict(state, {"fit": {
            "type": "score",
            "instructions": f"{method['name']}を今から始める適切さ。適用条件：{method['criterion']} 注意：{method['limit']} 入力にない条件は満たすと仮定しない。",
            "criteria": ["低：目的に合わない、または必須条件が満たされない。", "中：目的には合いそうだが適用条件が不明。暫定提案。", "高：目的と試験・データ・運用条件が具体的で、この手法の適用条件を満たす。"],
        }}, max_len=4096, head_max_len=640)["answers"]["fit"]
        fit_value = float(suitability["score"])
        degree = "高" if fit_value >= 1.5 else "中" if fit_value >= .5 else "低"
        probabilities = choice["probabilities"]
        ordered = sorted(probabilities.values(), reverse=True)
        close = ordered[0] - ordered[1] < .15
        # If the purpose policy disagrees with the direct classifier, show a
        # provisional answer instead of hiding the model disagreement.
        disagreement = key != choice["choice"]
        underspecified = len(state) < 35 and purpose is None
        delayed_online = key == "online" and bool(re.search(r"(?:結果|品質).{0,25}(?:一週間|数日|翌日|\d+日).{0,10}後", state)) and bool(re.search(r"(?:数分|毎分|即時|リアルタイム)", state))
        # This is a display policy, not a calibrated correctness probability.
        if (close or disagreement) and degree == "高":
            degree = "中"
        if underspecified or delayed_online:
            degree = "低"
        return {
            "input": text, "context": context,
            "method": method["name"], "method_id": key, "recommendation": degree,
            "provisional": degree != "高" or close or disagreement,
            "selection_basis": basis, "model_disagreement": disagreement,
            "insufficient_detail": underspecified, "delayed_feedback": delayed_online,
            "reason": method["reason"], "next_step": method["next"],
            "limitation": method["limit"], "check": method["check"],
            "close_candidates": close,
            "model_choice": choice, "model_suitability": suitability,
            "model_intents": {"window": first["window"], "update": first["update"]},
            "notice": "推奨度はモデルによる適用条件の評価です。正答率・成功確率ではありません。理由は選定手法の定型説明です。",
        }


def render(result: dict) -> str:
    suffix = "（暫定）" if result["provisional"] else ""
    lines = [f"おすすめ：{result['method']}{suffix}", f"推奨度：{result['recommendation']}", "",
             result["reason"], "", "最初の進め方", result["next_step"], "",
             "適用条件・限界", result["limitation"], "", "確認したいこと", result["check"]]
    if result["close_candidates"]:
        lines.extend(["", "候補間のモデル出力が近いため、試験の負担や継続更新の必要性を補足して再判定してください。"])
    if result["model_disagreement"]:
        lines.extend(["", "目的別の判定と4択判定に違いがあります。目的を優先して選定した暫定提案です。"])
    if result.get("insufficient_detail"):
        lines.extend(["", "目的だけでは適用条件を判断できません。対象・因子・試験の負担・継続更新の必要性を補足してください。"])
    if result.get("delayed_feedback"):
        lines.extend(["", "結果の遅れに対して工程変化が速く、即時追従の前提が満たされていません。品質結果の遅れを解決する検討が先です。"])
    lines.extend(["", "選定根拠：" + result["selection_basis"]])
    lines.extend(["", result["notice"], "4手法には重なりがあり、ここでは着手する手法を1つ提案します。"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Laya製造業手法アドバイザー")
    parser.add_argument("text", nargs="?", help="やりたいこと。省略すると入力画面を開きます")
    parser.add_argument("--context", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.text is None:
        from gui import run
        run()
    else:
        result = Advisor().recommend(args.text, args.context)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))


if __name__ == "__main__":
    main()
