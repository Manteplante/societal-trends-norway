"""Chart styling the pages share — one palette, one layout pass.

Pages draw with `plotly.express`; this module only decides how the result
looks, so a change here lands on every chart at once.

The eight hues are a validated categorical order: on this app's white surface
(`.streamlit/config.toml` pins a light theme) they clear the colour-vision
separation, lightness and chroma checks on adjacent pairs. Two consequences
the pages have to honour:

- **Hues are assigned in order and never cycled.** A ninth series would repeat
  the first hue, so pages cap their series count at `SERIES_LIMIT`. Pass
  `color_discrete_sequence=PALETTE` *and* a `category_orders` entry listing at
  most `SERIES_LIMIT` categories: plotly maps colour by position in that list,
  so a longer list silently wraps back to the first hue. Keeping the list
  stable is also what stops a filter from repainting the series that survive
  it — colour follows the entity, not its rank.
- **Three hues sit below 3:1 contrast against white.** That is legal only with
  relief — the reader must be able to get the numbers without the colour. Every
  page keeps its table reachable in the "Vis data" expander for that reason;
  don't remove it.
"""

from __future__ import annotations

from typing import Iterable, Optional

PALETTE = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]

SERIES_LIMIT = len(PALETTE)

SURFACE = "#ffffff"
GRID = "#f0efec"
AXIS = "#e6e5e1"
INK = "#0b0b0b"
INK_MUTED = "#52514e"


def _floats(values) -> list[float]:
    """The real numbers in a trace's x or y — empty for a date or category axis."""
    numbers = []
    for value in values if values is not None else ():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number:  # drops NaN
            numbers.append(number)
    return numbers


def _whole_number_ticks(fig, axis: str, tickformat: str) -> None:
    """Integer tick labels on a numeric axis, never a decimal.

    Left alone when the axis holds dates or categories. `dtick=1` is forced on a
    narrow range because plotly's automatic ticks would otherwise step in
    fractions and, once formatted as integers, print the same label twice.
    """
    # `or []` would test a numpy array for truthiness, which raises — hence the
    # explicit None check on each trace's array.
    values = []
    for trace in fig.data:
        series = getattr(trace, axis, None)
        if series is not None:
            values.extend(series)
    numbers = _floats(values)
    if not numbers:
        return

    update = fig.update_xaxes if axis == "x" else fig.update_yaxes
    update(tickformat=tickformat)
    if max(numbers) - min(numbers) < 5:
        update(dtick=1)


def cap(names: Iterable[str]) -> list[str]:
    """At most `SERIES_LIMIT` series — past that the palette would repeat a hue."""
    return list(names)[:SERIES_LIMIT]


def style(fig, *, area: bool = False, max_xticks: Optional[int] = None):
    """Recessive grid and axes, thin marks, one tooltip listing every series.

    `max_xticks` caps the labels on a categorical x axis. Plotly labels every
    category by default, which collides once there are more than a dozen or so.
    """
    fig.update_layout(
        colorway=PALETTE,
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        font=dict(color=INK_MUTED, size=13),
        title=dict(font=dict(color=INK, size=17), x=0, xanchor="left"),
        # Legend above the plot, so identity is never carried by colour alone.
        # A lone series needs no legend box — the title already names it.
        showlegend=len(fig.data) > 1,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""),
        margin=dict(t=90, r=24, b=48, l=64),
        hovermode="x unified",  # the crosshair finds the x, every series reads out
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=AXIS, ticks="outside", tickcolor=AXIS)
    if max_xticks:
        fig.update_xaxes(tickmode="auto", nticks=max_xticks)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, showline=False)

    # Whole numbers on both axes: thousands separators on the measure, none on
    # the x axis, where a numeric axis is always a year (2015, never 2,015).
    _whole_number_ticks(fig, "y", ",d")
    _whole_number_ticks(fig, "x", "d")

    if area:
        # A 2px surface gap between stacked fills, so the bands read as separate
        # shapes instead of one continuous block. Plotly derives an area's fill
        # from its line colour, so the hue has to be pinned to `fillcolor` first
        # — whitening the line on its own would render every band white.
        for trace in fig.data:
            hue = trace.fillcolor or trace.line.color
            trace.update(fillcolor=hue, line=dict(width=2, color=SURFACE))
    else:
        fig.update_traces(line=dict(width=2), marker=dict(size=8))

    return fig
