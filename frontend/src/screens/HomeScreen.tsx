import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { leagueApi, matchupApi, teamApi } from '@/api/endpoints';
import { Card } from '@/components/Card';
import { Spinner } from '@/components/Spinner';
import { colors, font, spacing } from '@/theme';

interface NewsItem {
  id: string;
  title: string;
  source: string;
  published_at: string;
  url: string;
}

interface MatchupTeam {
  id: string;
  name: string;
  wins: number;
  losses: number;
  ties: number;
}

interface CurrentMatchup {
  id: string;
  week_number: number;
  home_team: MatchupTeam;
  away_team: MatchupTeam;
  home_score?: number;
  away_score?: number;
  status: string;
}

export function HomeScreen() {
  const navigation = useNavigation<any>();
  const [news, setNews] = useState<NewsItem[]>([]);
  const [matchup, setMatchup] = useState<CurrentMatchup | null>(null);
  const [leagueInfo, setLeagueInfo] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [newsRes, matchupRes, leagueRes] = await Promise.allSettled([
        leagueApi.news(10),
        matchupApi.current(),
        leagueApi.get(),
      ]);
      if (newsRes.status === 'fulfilled') setNews(newsRes.value.data);
      if (matchupRes.status === 'fulfilled') setMatchup(matchupRes.value.data);
      if (leagueRes.status === 'fulfilled') setLeagueInfo(leagueRes.value.data);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  if (loading) return <Spinner fullscreen />;

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      {leagueInfo && (
        <Text style={styles.leagueName}>{leagueInfo.name}</Text>
      )}

      {matchup && (
        <TouchableOpacity onPress={() => navigation.navigate('Matchup', { id: matchup.id })}>
          <Card style={styles.matchupCard}>
            <Text style={styles.sectionLabel}>WEEK {matchup.week_number}</Text>
            <View style={styles.matchupRow}>
              <View style={styles.matchupTeam}>
                <Text style={styles.teamName} numberOfLines={1}>{matchup.home_team.name}</Text>
                <Text style={styles.record}>
                  {matchup.home_team.wins}-{matchup.home_team.losses}-{matchup.home_team.ties}
                </Text>
              </View>
              <View style={styles.scoreBlock}>
                {matchup.home_score !== undefined ? (
                  <Text style={styles.score}>
                    {matchup.home_score} – {matchup.away_score}
                  </Text>
                ) : (
                  <Text style={styles.scoreVs}>vs</Text>
                )}
                <Text style={styles.matchupStatus}>{matchup.status}</Text>
              </View>
              <View style={[styles.matchupTeam, styles.right]}>
                <Text style={[styles.teamName, { textAlign: 'right' }]} numberOfLines={1}>
                  {matchup.away_team.name}
                </Text>
                <Text style={[styles.record, { textAlign: 'right' }]}>
                  {matchup.away_team.wins}-{matchup.away_team.losses}-{matchup.away_team.ties}
                </Text>
              </View>
            </View>
          </Card>
        </TouchableOpacity>
      )}

      <Text style={styles.sectionHeader}>League News</Text>
      {news.map((item) => (
        <Card key={item.id} style={styles.newsCard}>
          <Text style={styles.newsTitle} numberOfLines={3}>{item.title}</Text>
          <Text style={styles.newsMeta}>{item.source} · {new Date(item.published_at).toLocaleDateString()}</Text>
        </Card>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing[4], gap: spacing[3] },
  leagueName: {
    fontFamily: font.heading,
    fontSize: 24,
    color: colors.text,
    marginBottom: spacing[2],
  },
  sectionLabel: {
    fontFamily: font.bodySemi,
    fontSize: 11,
    color: colors.primary,
    letterSpacing: 1,
    marginBottom: spacing[2],
  },
  sectionHeader: {
    fontFamily: font.heading,
    fontSize: 18,
    color: colors.text,
    marginTop: spacing[4],
  },
  matchupCard: { gap: spacing[2] },
  matchupRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[2],
  },
  matchupTeam: { flex: 1 },
  right: { alignItems: 'flex-end' },
  teamName: {
    fontFamily: font.bodyMed,
    fontSize: 15,
    color: colors.text,
  },
  record: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.textSub,
  },
  scoreBlock: {
    alignItems: 'center',
    minWidth: 72,
  },
  score: {
    fontFamily: font.mono,
    fontSize: 20,
    color: colors.text,
  },
  scoreVs: {
    fontFamily: font.body,
    fontSize: 16,
    color: colors.textDim,
  },
  matchupStatus: {
    fontFamily: font.body,
    fontSize: 11,
    color: colors.textSub,
    marginTop: 2,
    textTransform: 'capitalize',
  },
  newsCard: { gap: 4 },
  newsTitle: {
    fontFamily: font.bodyMed,
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  newsMeta: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.textSub,
  },
});
