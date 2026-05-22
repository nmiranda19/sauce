import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { leagueApi } from '@/api/endpoints';
import { Spinner } from '@/components/Spinner';
import { colors, font, spacing, radius } from '@/theme';

interface Standing {
  rank: number;
  team_id: string;
  team_name: string;
  wins: number;
  losses: number;
  ties: number;
  points: number;
  category_wins: number;
}

export function StandingsScreen() {
  const navigation = useNavigation<any>();
  const [standings, setStandings] = useState<Standing[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await leagueApi.standings();
      setStandings(res.data);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  if (loading) return <Spinner fullscreen />;

  return (
    <FlatList
      style={styles.list}
      contentContainerStyle={styles.content}
      data={standings}
      keyExtractor={(item) => item.team_id}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.rankCol}>#</Text>
          <Text style={styles.teamCol}>Team</Text>
          <Text style={styles.statCol}>W</Text>
          <Text style={styles.statCol}>L</Text>
          <Text style={styles.statCol}>T</Text>
          <Text style={styles.ptsCol}>PTS</Text>
        </View>
      }
      renderItem={({ item, index }) => (
        <TouchableOpacity
          style={[styles.row, index % 2 === 0 && styles.rowAlt]}
          onPress={() => navigation.navigate('TeamDetail', { id: item.team_id })}
          activeOpacity={0.7}
        >
          <Text style={[styles.rankCol, styles.rankText, item.rank <= 4 && styles.playoff]}>
            {item.rank}
          </Text>
          <Text style={[styles.teamCol, styles.teamText]} numberOfLines={1}>
            {item.team_name}
          </Text>
          <Text style={[styles.statCol, styles.statText]}>{item.wins}</Text>
          <Text style={[styles.statCol, styles.statText]}>{item.losses}</Text>
          <Text style={[styles.statCol, styles.statText]}>{item.ties}</Text>
          <Text style={[styles.ptsCol, styles.ptsText]}>{item.points ?? item.category_wins}</Text>
        </TouchableOpacity>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { flex: 1, backgroundColor: colors.bg },
  content: { paddingBottom: spacing[8] },
  header: {
    flexDirection: 'row',
    paddingHorizontal: spacing[4],
    paddingVertical: spacing[3],
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.bg,
  },
  row: {
    flexDirection: 'row',
    paddingHorizontal: spacing[4],
    paddingVertical: spacing[3],
    alignItems: 'center',
    backgroundColor: colors.card,
  },
  rowAlt: { backgroundColor: colors.bg },
  rankCol: {
    width: 28,
    fontFamily: font.bodySemi,
    fontSize: 12,
    color: colors.textSub,
  },
  rankText: { fontFamily: font.mono, fontSize: 14, color: colors.textSub },
  playoff: { color: colors.primary },
  teamCol: { flex: 1, fontFamily: font.bodySemi, fontSize: 12, color: colors.textSub },
  teamText: { fontFamily: font.bodyMed, fontSize: 14, color: colors.text },
  statCol: { width: 32, textAlign: 'center', fontFamily: font.bodySemi, fontSize: 12, color: colors.textSub },
  statText: { fontFamily: font.mono, fontSize: 14, color: colors.text },
  ptsCol: { width: 40, textAlign: 'right', fontFamily: font.bodySemi, fontSize: 12, color: colors.textSub },
  ptsText: { fontFamily: font.mono, fontSize: 14, color: colors.primary },
});
