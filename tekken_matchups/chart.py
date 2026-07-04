from abc import ABC, abstractmethod


def lerp(a: int | float, b: int | float, t: float) -> float:
    return (1 - t) * a + (t * b)


class TableCell(ABC):
    @abstractmethod
    def cell_body(self) -> str: ...

    @abstractmethod
    def background_color(self) -> str: ...

    def tooltip_body(self) -> str | None:
        return None


class TotalGamesCell(TableCell):
    def __init__(self, n_games: int, global_max_n_games: int):
        self.n_games = n_games
        self.global_max_n_games = global_max_n_games

    def background_color(self) -> str:
        diff_t = float(self.n_games) / float(self.global_max_n_games)
        r = round(lerp(0xFF, 0x00, diff_t))
        g = round(lerp(0xFF, 0x00, diff_t))
        b = 0xFF
        return "#{:02x}{:02x}{:02x}".format(r, g, b)

    def cell_body(self) -> str:
        if self.n_games < 1_000:
            return "{:,}".format(self.n_games)
        else:
            return "{: >3.1f}k".format(self.n_games / 1000)


class MatchupCell(TableCell):
    def __init__(
        self,
        c1: str,
        c2: str,
        matchup_diff: float,
        n_games: int,
        global_min_diff: float,
        global_max_diff: float,
    ):
        self.c1 = c1
        self.c2 = c2
        self.matchup_diff = matchup_diff
        self.n_games = n_games
        self.global_min_diff = global_min_diff
        self.global_max_diff = global_max_diff

    def background_color(self) -> str:
        if self.matchup_diff < 0.0:
            self.global_max_diff = 0.0
            color_min = (0xFF, 0x00, 0x00)
            color_max = (0xFF, 0xFF, 0xFF)
        else:
            self.global_min_diff = 0.0
            color_min = (0xFF, 0xFF, 0xFF)
            color_max = (0x00, 0xFF, 0x00)

        if self.matchup_diff == self.global_min_diff:
            diff_t = 0.0
        elif self.matchup_diff == self.global_max_diff:
            diff_t = 1.0
        else:
            diff_t = (self.matchup_diff - self.global_min_diff) / (
                self.global_max_diff - self.global_min_diff
            )
        r = round(lerp(color_min[0], color_max[0], diff_t))
        g = round(lerp(color_min[1], color_max[1], diff_t))
        b = round(lerp(color_min[2], color_max[2], diff_t))

        return "#{:02x}{:02x}{:02x}".format(r, g, b)

    def cell_body(self) -> str:
        return f"{self.matchup_diff: >+4.1f}".replace(" ", "&nbsp;")

    def tooltip_body(self) -> str | None:
        return f"""
            <div><b>{self.c1}</b> has a</div>
            <div><b>{self.matchup_diff:+.3f}</b> matchup</div>
            <div>versus <b>{self.c2}</b></div>
            <div class="smaller">{self.n_games:,} games</div>
        """
