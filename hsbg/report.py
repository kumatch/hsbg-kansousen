"""Static single-file HTML report (docs/analysis-and-visualization.md §2). Presentation only: numbers come from metrics.py,
figures from charts.py. plotly.js is embedded so the file opens offline."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

from . import charts, labels, metrics
from .normalize import Tables

_CSS = """
body { font-family: Segoe UI, Meiryo, sans-serif; margin: 0; background: #f6f7f9; color: #212529; }
header { background: #1d3557; color: #fff; padding: 20px 32px; }
header h1 { margin: 0 0 6px 0; font-size: 22px; }
header .meta { opacity: .85; font-size: 14px; }
main { max-width: 1180px; margin: 0 auto; padding: 24px 32px 48px; }
section { background: #fff; border-radius: 8px; padding: 18px 22px; margin: 18px 0;
          box-shadow: 0 1px 3px rgba(0,0,0,.08); }
section h2 { margin: 0 0 12px 0; font-size: 17px; color: #1d3557; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.kpi { background: #f1f5f9; border-radius: 8px; padding: 12px 14px; }
.kpi .label { font-size: 12px; color: #6c757d; }
.kpi .value { font-size: 24px; font-weight: 600; margin-top: 4px; }
table.data { border-collapse: collapse; width: 100%; font-size: 13px; }
table.data th, table.data td { border-bottom: 1px solid #e9ecef; padding: 6px 8px; text-align: left; }
table.data th { background: #f1f5f9; }
table.data tr.faded { color: #9aa3ad; }
.warn { color: #b02a37; font-size: 13px; }
.note { color: #6c757d; font-size: 13px; margin: 0 0 8px 0; }
"""


def _fig_html(fig: go.Figure) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False})


def _kpi(label: str, value: object) -> str:
    return f'<div class="kpi"><div class="label">{html.escape(label)}</div><div class="value">{value}</div></div>'


def _fmt_rate(v: float | None) -> str:
    return "-" if v is None else f"{v:.0%}"


def _table(
    df: pd.DataFrame, columns: dict[str, str], faded_when: str | None = None, faded_below: int = 3
) -> str:
    if df.empty:
        return '<p class="warn">データなし</p>'
    head = "".join(f"<th>{html.escape(t)}</th>" for t in columns.values())
    rows = []
    for _, r in df.iterrows():
        cls = ' class="faded"' if faded_when and r[faded_when] < faded_below else ""
        cells = "".join(f"<td>{_cell(r[c])}</td>" for c in columns)
        rows.append(f"<tr{cls}>{cells}</tr>")
    return (
        f'<table class="data"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )


def _cell(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v) >= 1 else f"{v:.0%}"
    return html.escape(str(v))


def _type_labels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ("minion_type", "opp_type", "my_type"):
        if c in out:
            out[c] = out[c].map(labels.minion_type)
    return out


def build_report(
    tables: Tables,
    *,
    excluded_incomplete: int = 0,
    title: str = "HSBG 戦績レポート",
    generated_at: datetime | None = None,
) -> str:
    k = metrics.kpis(tables)
    generated_at = generated_at or datetime.now()
    period = (
        f"{k['period_start']:%Y-%m-%d} – {k['period_end']:%Y-%m-%d}" if k["games"] else "ゲームなし"
    )

    hero = metrics.hero_stats(tables)
    type_avail = _type_labels(metrics.type_availability_stats(tables))
    type_final = _type_labels(metrics.minion_type_stats(tables))
    opp = metrics.opponent_hero_stats(tables)
    recent = metrics.recent_games(tables, 20).copy()
    recent["link"] = recent["path"].map(
        lambda p: f'<a href="{Path(p).as_uri()}">json</a>' if p else "-"
    )
    recent["status"] = recent["status"].map(labels.status)

    sections = [
        f"""<section><h2>KPI</h2><div class="kpis">
        {_kpi("ゲーム数", k["games"])}
        {_kpi("平均順位", k["avg_placement"] if k["avg_placement"] is not None else "-")}
        {_kpi("Top 4 率", _fmt_rate(k["top4_rate"]))}
        {_kpi("1 位率", _fmt_rate(k["first_rate"]))}
        {_kpi("MMR 増減", f"{k['mmr_change']:+d}" if k["mmr_change"] is not None else "-")}
        {_kpi("平均ゲーム時間", f"{k['avg_duration_min']} 分" if k["avg_duration_min"] else "-")}
        </div></section>""",
        f"<section><h2>MMR 推移</h2>{_fig_html(charts.mmr_line(metrics.mmr_progression(tables)))}"
        f"{_fig_html(charts.rolling_placement_line(metrics.rolling_avg_placement(tables)))}</section>",
        f"<section><h2>順位分布</h2>"
        f"{_fig_html(charts.placement_histogram(metrics.placement_distribution(tables)))}</section>",
        f"<section><h2>ヒーロー別成績</h2>{_table(hero, {'hero_name': 'ヒーロー', 'games': 'ゲーム数', 'avg_placement': '平均順位', 'top4_rate': 'Top 4 率', 'first_rate': '1 位率', 'mmr_change': 'MMR 増減'}, faded_when='games')}"
        f"{_fig_html(charts.hero_bar(hero))}</section>",
        f"<section><h2>種族</h2><p class='note'>主軸種族 = 盤面で最も多い種族。「使った」= 最終盤面の主軸にしたゲーム。</p>"
        f"{_table(type_avail, {'minion_type': '種族', 'offered_games': '出現したゲーム', 'offered_avg_placement': '出現時の平均順位', 'offered_top4_rate': '出現時の Top 4 率', 'played_games': '主軸にしたゲーム', 'pick_rate': '採用率', 'played_avg_placement': '使ったときの平均順位', 'not_played_avg_placement': '使わなかったときの平均順位'}, faded_when='played_games')}"
        f"{_fig_html(charts.type_offered_vs_played_bar(metrics.type_availability_stats(tables)))}"
        f"{_table(type_final, {'minion_type': '最終盤面の主軸', 'games': 'ゲーム数', 'avg_placement': '平均順位', 'top4_rate': 'Top 4 率', 'first_rate': '1 位率', 'median_commit_turn': '主軸を固めたターン（中央値）', 'avg_pivots': '方針転換（平均）', 'mmr_change': 'MMR 増減'}, faded_when='games')}"
        f"{_fig_html(charts.type_placement_bar(metrics.minion_type_stats(tables)))}"
        f"{_fig_html(charts.type_timeline_chart(metrics.type_timeline(tables)))}"
        f"{_fig_html(charts.type_matchup_heatmap(metrics.type_matchups(tables)))}</section>",
        f"<section><h2>ティア到達ターン</h2>{_fig_html(charts.tier_reach_box(metrics.tier_reach_turns(tables)))}</section>",
        f"<section><h2>ターン別 戦闘勝率</h2>{_fig_html(charts.combat_winrate_line(metrics.combat_winrate_by_turn(tables)))}</section>",
        f"<section><h2>体力の推移</h2>{_fig_html(charts.health_band(metrics.health_by_turn(tables)))}</section>",
        f"<section><h2>リロール</h2>{_fig_html(charts.reroll_scatter(metrics.reroll_vs_placement(tables)))}</section>",
        f"<section><h2>相手ヒーロー別 戦闘成績</h2>{_table(opp, {'opponent_hero_name': '相手ヒーロー', 'combats': '戦闘数', 'wins': '勝ち', 'losses': '負け', 'ties': '引き分け', 'win_rate': '勝率', 'avg_damage_taken': '平均被ダメージ'})}</section>",
        f"<section><h2>直近のゲーム</h2>{_table(recent, {'started_at': '開始', 'hero_name': 'ヒーロー', 'placement': '順位', 'mmr_before': 'MMR', 'mmr_delta': 'MMR 増減', 'final_tier': '最終ティア', 'total_turns': 'ターン数', 'status': '状態', 'link': 'ログ'})}</section>",
    ]
    excluded = (
        f"<span class='warn'> · 未完了ログ {excluded_incomplete} 件を除外</span>"
        if excluded_incomplete
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>{_CSS}</style><script>{get_plotlyjs()}</script></head>
<body><header><h1>{html.escape(title)}</h1>
<div class="meta">期間 {period} · {k["games"]} ゲーム · 生成 {generated_at:%Y-%m-%d %H:%M}{excluded}</div></header>
<main>{"".join(sections)}</main></body></html>"""


def write_report(html_text: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    return out
