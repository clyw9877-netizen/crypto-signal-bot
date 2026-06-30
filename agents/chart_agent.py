import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from typing import List, Dict

def draw_signal_chart(symbol, candles, signal, save_path=None):
    display_candles = candles[-60:] if len(candles) > 60 else candles
    n = len(display_candles)
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor('#0d0f1a')
    ax.set_facecolor('#0d0f1a')
    for i, c in enumerate(display_candles):
        bull = c['close'] >= c['open']
        col = '#26a69a' if bull else '#ef5350'
        wk = '#1a7a72' if bull else '#c0392b'
        ax.plot([i,i],[c['low'],c['high']],color=wk,linewidth=1.2,zorder=2)
        body_top = max(c['open'],c['close'])
        body_bot = min(c['open'],c['close'])
        body_h = max(body_top-body_bot, c['close']*0.0005)
        rect = plt.Rectangle((i-0.42,body_bot),0.84,body_h,facecolor=col,edgecolor=col,linewidth=0.5,zorder=3)
        ax.add_patch(rect)
    current_price = display_candles[-1]['close']
    entry = signal.get('price', current_price)
    sl = signal.get('sl', 0)
    tp = signal.get('tp', 0)
    confidence = signal.get('confidence', 0)
    direction = signal.get('signal', 'long')
    if sl: ax.hlines(sl, n-15, n+3, colors='#ff0055', linewidths=2, linestyles='--', alpha=0.9, zorder=5)
    if tp: ax.hlines(tp, n-15, n+3, colors='#00ff88', linewidths=2, linestyles='--', alpha=0.9, zorder=5)
    ax.hlines(entry, n-15, n+3, colors='#aa66ff', linewidths=2, linestyles='-', alpha=0.9, zorder=5)
    ax.hlines(current_price, 0, n, colors='#ffffff', linewidths=0.8, alpha=0.3)
    rr = signal.get('rr', 0)
    rsi = signal.get('rsi', 50)
    dir_text = "ЛОНГ" if direction == 'long' else "ШОРТ"
    info = "Сигнал: " + symbol + " " + dir_text + "\nУверенность: " + str(confidence) + "%\nВход: $" + str(round(entry,2)) + "\nSL: $" + str(round(sl,2)) + "\nTP: $" + str(round(tp,2)) + "\nRR: 1:" + str(round(rr,1)) + "\nRSI: " + str(round(rsi))
    props = dict(boxstyle='round', facecolor='#0a1520', alpha=0.95, edgecolor='#aa66ff', linewidth=1.5)
    ax.text(2, ax.get_ylim()[1] if ax.get_ylim()[1] else current_price*1.02, info, fontsize=9, color='#c0d8f0', verticalalignment='top', bbox=props, fontfamily='monospace', zorder=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x,p: '$'+'{:,.0f}'.format(x)))
    ax.tick_params(axis='y', colors='#3a5060', labelsize=8)
    ax.tick_params(axis='x', colors='#3a5060', labelsize=7)
    ax.set_xlim(-1, n+8)
    ax.grid(True, alpha=0.05, color='#ffffff', linewidth=0.5)
    for spine in ax.spines.values(): spine.set_color('#1a2535')
    ax.set_title(symbol + ' · 1ч · BingX | Уверенность: ' + str(confidence) + '% | ' + dir_text, color='#c0d8f0', fontsize=11, fontweight='bold', pad=10)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=130, bbox_inches='tight', facecolor='#0d0f1a')
        plt.close()
        return None
    else:
        buf = io.BytesIO()
        plt.savefig(buf, format='PNG', dpi=130, bbox_inches='tight', facecolor='#0d0f1a')
        plt.close()
        buf.seek(0)
        return buf.read()
