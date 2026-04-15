"""initial schema for MLB tables

Revision ID: 001
Revises:
Create Date: 2026-04-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("abbreviation", sa.String(length=8), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=True),
        sa.Column("venue_name", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "games",
        sa.Column("game_pk", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(length=8), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("game_datetime_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=True),
        sa.Column("venue_name", sa.String(length=256), nullable=True),
        sa.Column("lineups_json", sa.JSON(), nullable=True),
        sa.Column("boxscore_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("game_pk"),
    )
    op.create_table(
        "game_weather",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_pk", sa.Integer(), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("humidity_pct", sa.Float(), nullable=True),
        sa.Column("wind_speed_mps", sa.Float(), nullable=True),
        sa.Column("pressure_mbar", sa.Float(), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["game_pk"], ["games.game_pk"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_pk"),
    )
    op.create_table(
        "game_feature_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_pk", sa.Integer(), nullable=False),
        sa.Column("home_wins_roll", sa.Float(), nullable=True),
        sa.Column("away_wins_roll", sa.Float(), nullable=True),
        sa.Column("home_runs_avg_roll", sa.Float(), nullable=True),
        sa.Column("away_runs_avg_roll", sa.Float(), nullable=True),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("humidity_pct", sa.Float(), nullable=True),
        sa.Column("wind_speed_mps", sa.Float(), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("home_win", sa.Integer(), nullable=True),
        sa.Column("total_runs", sa.Float(), nullable=True),
        sa.Column("feature_vector_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["game_pk"], ["games.game_pk"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_pk"),
    )


def downgrade() -> None:
    op.drop_table("game_feature_snapshots")
    op.drop_table("game_weather")
    op.drop_table("games")
    op.drop_table("teams")
