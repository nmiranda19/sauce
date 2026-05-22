import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  Alert,
  FlatList,
} from 'react-native';
import { commissionerApi } from '@/api/endpoints';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { Spinner } from '@/components/Spinner';
import { colors, font, spacing, radius } from '@/theme';

export function CommissionerScreen() {
  const [pendingTrades, setPendingTrades] = useState<any[]>([]);
  const [log, setLog] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [advancing, setAdvancing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [tradesRes, logRes] = await Promise.allSettled([
        commissionerApi.pendingTrades(),
        commissionerApi.log(),
      ]);
      if (tradesRes.status === 'fulfilled') setPendingTrades(tradesRes.value.data);
      if (logRes.status === 'fulfilled') setLog(logRes.value.data);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  async function advanceWeek() {
    Alert.alert(
      'Advance Week?',
      'This will finalize the current week and move to the next. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Advance',
          onPress: async () => {
            setAdvancing(true);
            try {
              await commissionerApi.advanceWeek();
              load();
              Alert.alert('Done', 'Week advanced successfully.');
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Could not advance week.');
            } finally {
              setAdvancing(false);
            }
          },
        },
      ]
    );
  }

  async function approveTrade(tradeId: string) {
    try {
      await commissionerApi.approveTrade(tradeId);
      load();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not approve trade.');
    }
  }

  async function vetoTrade(tradeId: string) {
    Alert.alert('Veto trade?', '', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Veto',
        style: 'destructive',
        onPress: async () => {
          try {
            await commissionerApi.vetoTrade(tradeId);
            load();
          } catch (e: any) {
            Alert.alert('Error', e?.response?.data?.detail ?? 'Could not veto trade.');
          }
        },
      },
    ]);
  }

  if (loading) return <Spinner fullscreen />;

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      <Text style={styles.pageTitle}>Commissioner</Text>

      {/* Controls */}
      <Card style={styles.controlsCard}>
        <Text style={styles.sectionLabel}>LEAGUE CONTROLS</Text>
        <Button
          label="Advance Week"
          onPress={advanceWeek}
          loading={advancing}
          variant="secondary"
        />
      </Card>

      {/* Pending trades */}
      {pendingTrades.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionHeader}>Pending Trades ({pendingTrades.length})</Text>
          {pendingTrades.map((trade) => (
            <Card key={trade.id} style={styles.tradeCard}>
              <Text style={styles.tradeTeams}>
                {trade.proposing_team?.name} ↔ {trade.receiving_team?.name}
              </Text>
              <Text style={styles.tradeSummary}>
                {trade.players_from_me?.map((p: any) => p.full_name).join(', ')} for{' '}
                {trade.players_from_them?.map((p: any) => p.full_name).join(', ')}
              </Text>
              <View style={styles.tradeActions}>
                <Button
                  label="Approve"
                  onPress={() => approveTrade(trade.id)}
                  style={styles.tradeBtn}
                />
                <Button
                  label="Veto"
                  variant="danger"
                  onPress={() => vetoTrade(trade.id)}
                  style={styles.tradeBtn}
                />
              </View>
            </Card>
          ))}
        </View>
      )}

      {pendingTrades.length === 0 && (
        <Card>
          <Text style={styles.emptyText}>No trades pending review.</Text>
        </Card>
      )}

      {/* Activity log */}
      <View style={styles.section}>
        <Text style={styles.sectionHeader}>Activity Log</Text>
        {log.slice(0, 20).map((entry, i) => (
          <View key={i} style={styles.logEntry}>
            <Text style={styles.logAction}>{entry.action}</Text>
            <Text style={styles.logTime}>
              {new Date(entry.created_at).toLocaleDateString()} — {entry.commissioner_name}
            </Text>
            {entry.notes && <Text style={styles.logNotes}>{entry.notes}</Text>}
          </View>
        ))}
        {log.length === 0 && (
          <Text style={styles.emptyText}>No actions logged yet.</Text>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing[4], gap: spacing[4] },
  pageTitle: {
    fontFamily: font.heading,
    fontSize: 28,
    color: colors.text,
  },
  controlsCard: { gap: spacing[3] },
  sectionLabel: {
    fontFamily: font.bodySemi,
    fontSize: 11,
    color: colors.textSub,
    letterSpacing: 1,
  },
  section: { gap: spacing[3] },
  sectionHeader: {
    fontFamily: font.heading,
    fontSize: 18,
    color: colors.text,
  },
  tradeCard: { gap: spacing[3] },
  tradeTeams: { fontFamily: font.bodyMed, fontSize: 14, color: colors.text },
  tradeSummary: { fontFamily: font.body, fontSize: 13, color: colors.textSub },
  tradeActions: { flexDirection: 'row', gap: spacing[3] },
  tradeBtn: { flex: 1 },
  emptyText: { fontFamily: font.body, fontSize: 14, color: colors.textSub },
  logEntry: {
    paddingVertical: spacing[3],
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 4,
  },
  logAction: { fontFamily: font.bodyMed, fontSize: 14, color: colors.text },
  logTime: { fontFamily: font.body, fontSize: 12, color: colors.textSub },
  logNotes: { fontFamily: font.body, fontSize: 13, color: colors.textSub, fontStyle: 'italic' },
});
