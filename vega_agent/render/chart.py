"""Matplotlib chart rendering for markdown.

Responsibilities:
- Render line/bar charts with the same Base64 data-URI approach as the original demo.
- Annotate extrema for line charts.

Used by:
- ``app_gradio`` when the plan requests a chart.
Matplotlib 画折线图/柱状图
标注最高/最低点
转成 Base64 图片嵌入 Markdown
"""

import base64
import io

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd


plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def render_chart_markdown(df: pd.DataFrame, chart_type: str, x_col: str, y_col: str) -> str:
    if chart_type not in ['line', 'bar'] or df.empty or x_col not in df.columns or y_col not in df.columns:
        return ""

    plot_df = df.copy()
    plot_df[y_col] = pd.to_numeric(plot_df[y_col], errors="coerce")
    plot_df = plot_df.dropna(subset=[y_col])
    if plot_df.empty:
        return ""

    try:
        converted_x = pd.to_datetime(plot_df[x_col], errors="coerce")
        if converted_x.notna().mean() > 0.8:
            plot_df[x_col] = converted_x.dt.strftime('%Y-%m-%d')
    except Exception:
        pass

    fig, ax = plt.subplots(figsize=(10, 5))
    try:
        if chart_type == 'line':
            ax.plot(plot_df[x_col].astype(str), plot_df[y_col], marker='o', markersize=6, linewidth=2, color='#4A90E2')
            max_idx, min_idx = plot_df[y_col].idxmax(), plot_df[y_col].idxmin()
            ax.annotate(f'最高: {plot_df.loc[max_idx, y_col]:,.2f}',
                        xy=(str(plot_df.loc[max_idx, x_col]), plot_df.loc[max_idx, y_col]), xytext=(0, 10),
                        textcoords='offset points', ha='center', color='red', fontweight='bold')
            ax.annotate(f'最低: {plot_df.loc[min_idx, y_col]:,.2f}',
                        xy=(str(plot_df.loc[min_idx, x_col]), plot_df.loc[min_idx, y_col]), xytext=(0, -15),
                        textcoords='offset points', ha='center', color='green', fontweight='bold')
        else:
            ax.bar(plot_df[x_col].astype(str), plot_df[y_col], color='#4A90E2')

        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(f"{y_col} by {x_col}", fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.6)
        plt.xticks(rotation=45)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120)
        buf.seek(0)
        b64_encoded = base64.b64encode(buf.read()).decode('utf-8')
        return f"\n\n![图表](data:image/png;base64,{b64_encoded})"
    finally:
        plt.close(fig)

