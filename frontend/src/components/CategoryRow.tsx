import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, font, spacing } from '@/theme';

const CATEGORY_LABELS: Record<string, string> = {
  goals:               'Goals',
  assists:             'Assists',
  plus_minus:          '+/-',
  shots_on_goal:       'Shots',
  defenseman_points:   'D Points',
  special_teams_points:'PP/SH Pts',
  average_toi:         'Avg TOI',
  goalie_wins:         'G Wins',
  gaa:                 'GAA',
  save_pct:            'SV%',
};

interface CategoryResult {
  category: string;
  home_value: number;
  away_value: number;
  winner: 'home' | 'away' | 'tie';
}

interface Props {
  result: CategoryResult;
  homeTeamName: string;
  awayTeamName: string;
  perspective?: 'home' | 'away';
}

function fmt(cat: string, val: number): string {
  if (cat === 'gaa') return val.toFixed(2);
  if (cat === 'save_pct') return val.toFixed(3).replace('0.', '.');
  if (cat === 'average_toi') {
    const mins = Math.floor(val);
    const secs = Math.round((val - mins) * 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
  return Number.isInteger(val) ? String(val) : val.toFixed(1);
}

export function CategoryRow({ result, perspective }: Props) {
  const { category, home_value, away_value, winner } = result;
  const label = CATEGORY_LABELS[category] ?? category;

  const homeWon = winner === 'home';
  const awayWon = winner === 'away';
  const tied    = winner === 'tie';

  const myWin =
    perspective === 'home' ? homeWon :
    perspective === 'away' ? awayWon :
    false;

  return (
    <View style={styles.row}>
      <Text style={[styles.value, homeWon && styles.winner, !homeWon && !tied && styles.loser]}>
        {fmt(category, home_value)}
      </Text>
      <View style={styles.middle}>
        <Text style={styles.label}>{label}</Text>
        {tied && <View style={styles.tieDot} />}
        {!tied && <View style={[styles.winLine, myWin ? styles.winLineActive : styles.winLineInert]} />}
      </View>
      <Text style={[styles.value, styles.right, awayWon && styles.winner, !awayWon && !tied && styles.loser]}>
        {fmt(category, away_value)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing[2],
  },
  value: {
    fontFamily: font.mono,
    fontSize: 14,
    color: colors.text,
    width: 64,
  },
  right: {
    textAlign: 'right',
  },
  winner: {
    color: colors.primary,
    fontFamily: font.bodySemi,
  },
  loser: {
    color: colors.textDim,
  },
  middle: {
    flex: 1,
    alignItems: 'center',
    gap: 4,
  },
  label: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.textSub,
  },
  tieDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.tie,
  },
  winLine: {
    height: 2,
    width: 32,
    borderRadius: 1,
  },
  winLineActive: {
    backgroundColor: colors.primary,
  },
  winLineInert: {
    backgroundColor: colors.border,
  },
});
