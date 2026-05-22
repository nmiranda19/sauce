import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { matchupApi } from '@/api/endpoints';
import { CategoryRow } from '@/components/CategoryRow';
import { Card } from '@/components/Card';
import { Spinner } from '@/components/Spinner';
import { colors, font, spacing } from '@/theme';

interface Props {
  route?: { params?: { id?: string } };
}

export function MatchupScreen({ route }: Props) {
  const matchupId = route?.params?.id;
  const [matchup, setMatchup] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [week, setWeek] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      let res;
      if (matchupId) {
        res = await matchupApi.get(matchupId);
      } else {
        res = await matchupApi.current();
      }
      setMatchup(res.data);
      if (!matchupId && res.data?.week_number) {
        setWeek(res.data.week_number);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [matchupId]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  if (loading) return <Spinner fullscreen />;

  if (!matchup) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>No matchup found.</Text>
      </View>
    );
  }

  const { home_team, away_team, category_results, home_score, away_score, status, week_number } = matchup;
  const homeWins = home_score > away_score;
  const awayWins = away_score > home_score;

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      <Text style={styles.weekLabel}>WEEK {week_number}</Text>

      {/* Score header */}
      <Card style={styles.scoreCard}>
        <View style={styles.scoreRow}>
          <View style={styles.teamBlock}>
            <Text style={[styles.teamName, homeWins && styles.teamWinner]} numberOfLines={2}>
              {home_team?.name}
            </Text>
            <Text style={[styles.scoreNum, homeWins && styles.scoreWinner]}>
              {home_score ?? 0}
            </Text>
          </View>
          <View style={styles.divider}>
            <Text style={styles.vs}>—</Text>
            <Text style={styles.statusText}>{status}</Text>
          </View>
          <View style={[styles.teamBlock, styles.rightBlock]}>
            <Text style={[styles.teamName, styles.rightText, awayWins && styles.teamWinner]} numberOfLines={2}>
              {away_team?.name}
            </Text>
            <Text style={[styles.scoreNum, styles.rightText, awayWins && styles.scoreWinner]}>
              {away_score ?? 0}
            </Text>
          </View>
        </View>
      </Card>

      {/* Category breakdown */}
      {category_results && category_results.length > 0 && (
        <Card style={styles.categoriesCard}>
          <Text style={styles.sectionLabel}>CATEGORIES</Text>
          {category_results.map((r: any) => (
            <CategoryRow
              key={r.category}
              result={r}
              homeTeamName={home_team?.name ?? ''}
              awayTeamName={away_team?.name ?? ''}
            />
          ))}
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing[4], gap: spacing[3] },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  emptyText: { fontFamily: font.body, fontSize: 16, color: colors.textSub },
  weekLabel: {
    fontFamily: font.bodySemi,
    fontSize: 11,
    color: colors.primary,
    letterSpacing: 1,
  },
  scoreCard: {},
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[3],
  },
  teamBlock: { flex: 1, gap: spacing[1] },
  rightBlock: { alignItems: 'flex-end' },
  teamName: {
    fontFamily: font.bodyMed,
    fontSize: 14,
    color: colors.textSub,
  },
  teamWinner: { color: colors.text },
  rightText: { textAlign: 'right' },
  scoreNum: {
    fontFamily: font.heading,
    fontSize: 36,
    color: colors.textDim,
  },
  scoreWinner: { color: colors.primary },
  divider: { alignItems: 'center', gap: 4 },
  vs: {
    fontFamily: font.mono,
    fontSize: 20,
    color: colors.border,
  },
  statusText: {
    fontFamily: font.body,
    fontSize: 11,
    color: colors.textSub,
    textTransform: 'capitalize',
  },
  categoriesCard: { gap: 2 },
  sectionLabel: {
    fontFamily: font.bodySemi,
    fontSize: 11,
    color: colors.textSub,
    letterSpacing: 1,
    marginBottom: spacing[2],
  },
});
