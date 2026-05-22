import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  Modal,
  Alert,
  ScrollView,
} from 'react-native';
import { tradeApi, teamApi } from '@/api/endpoints';
import { Button } from '@/components/Button';
import { PlayerRow } from '@/components/PlayerRow';
import { Card } from '@/components/Card';
import { Spinner } from '@/components/Spinner';
import { colors, font, spacing, radius } from '@/theme';

const STATUS_COLOR: Record<string, string> = {
  pending:   colors.tie,
  approved:  colors.win,
  rejected:  colors.loss,
  vetoed:    colors.loss,
  withdrawn: colors.textDim,
  accepted:  colors.win,
};

export function TradesScreen() {
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<any>(null);
  const [impact, setImpact] = useState<any>(null);
  const [responding, setResponding] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await tradeApi.list();
      setTrades(res.data);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  async function openTrade(trade: any) {
    setSelectedTrade(trade);
    try {
      const res = await tradeApi.impact(trade.id);
      setImpact(res.data);
    } catch {
      setImpact(null);
    }
  }

  async function respond(accept: boolean) {
    if (!selectedTrade) return;
    setResponding(true);
    try {
      await tradeApi.respond(selectedTrade.id, accept);
      setSelectedTrade(null);
      setImpact(null);
      load();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not respond to trade.');
    } finally {
      setResponding(false);
    }
  }

  async function withdraw() {
    if (!selectedTrade) return;
    Alert.alert('Withdraw trade?', '', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Withdraw',
        style: 'destructive',
        onPress: async () => {
          try {
            await tradeApi.withdraw(selectedTrade.id);
            setSelectedTrade(null);
            load();
          } catch (e: any) {
            Alert.alert('Error', e?.response?.data?.detail ?? 'Could not withdraw.');
          }
        },
      },
    ]);
  }

  if (loading) return <Spinner fullscreen />;

  return (
    <View style={styles.container}>
      <FlatList
        data={trades}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
        renderItem={({ item }) => (
          <TouchableOpacity onPress={() => openTrade(item)} activeOpacity={0.75}>
            <Card style={styles.tradeCard}>
              <View style={styles.tradeHeader}>
                <Text style={styles.tradeTeams}>
                  {item.proposing_team?.name} → {item.receiving_team?.name}
                </Text>
                <Text style={[styles.tradeStatus, { color: STATUS_COLOR[item.status] ?? colors.textSub }]}>
                  {item.status}
                </Text>
              </View>
              <Text style={styles.tradeSummary}>
                {item.players_from_me?.map((p: any) => p.full_name).join(', ')} for{' '}
                {item.players_from_them?.map((p: any) => p.full_name).join(', ')}
              </Text>
            </Card>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text style={styles.empty}>No trades yet.</Text>
        }
      />

      {/* Trade detail modal */}
      <Modal visible={!!selectedTrade} animationType="slide" presentationStyle="pageSheet">
        <View style={styles.modal}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Trade Details</Text>
            <TouchableOpacity onPress={() => { setSelectedTrade(null); setImpact(null); }}>
              <Text style={styles.modalClose}>Close</Text>
            </TouchableOpacity>
          </View>

          <ScrollView contentContainerStyle={styles.modalBody}>
            {selectedTrade && (
              <>
                <View style={styles.section}>
                  <Text style={styles.sectionLabel}>
                    FROM {selectedTrade.proposing_team?.name?.toUpperCase()}
                  </Text>
                  {selectedTrade.players_from_me?.map((p: any) => (
                    <PlayerRow key={p.id} player={p} />
                  ))}
                </View>

                <View style={styles.section}>
                  <Text style={styles.sectionLabel}>
                    FROM {selectedTrade.receiving_team?.name?.toUpperCase()}
                  </Text>
                  {selectedTrade.players_from_them?.map((p: any) => (
                    <PlayerRow key={p.id} player={p} />
                  ))}
                </View>

                {impact && (
                  <View style={styles.section}>
                    <Text style={styles.sectionLabel}>SEASON STATS</Text>
                    {Object.entries(impact).map(([playerId, stats]: any) => (
                      <View key={playerId} style={styles.impactRow}>
                        <Text style={styles.impactName}>{stats.full_name}</Text>
                        <Text style={styles.impactStats}>
                          {stats.goals}G {stats.assists}A {stats.points}PTS
                        </Text>
                      </View>
                    ))}
                  </View>
                )}

                {selectedTrade.status === 'pending' && (
                  <View style={styles.actions}>
                    {selectedTrade.can_respond && (
                      <>
                        <Button label="Accept" onPress={() => respond(true)} loading={responding} />
                        <Button label="Decline" variant="danger" onPress={() => respond(false)} />
                      </>
                    )}
                    {selectedTrade.can_withdraw && (
                      <Button label="Withdraw" variant="ghost" onPress={withdraw} />
                    )}
                  </View>
                )}
              </>
            )}
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { padding: spacing[4], gap: spacing[3] },
  tradeCard: { gap: spacing[2] },
  tradeHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  tradeTeams: { fontFamily: font.bodyMed, fontSize: 14, color: colors.text, flex: 1 },
  tradeStatus: { fontFamily: font.bodySemi, fontSize: 12, textTransform: 'capitalize' },
  tradeSummary: { fontFamily: font.body, fontSize: 13, color: colors.textSub },
  empty: { fontFamily: font.body, fontSize: 15, color: colors.textSub, textAlign: 'center', marginTop: spacing[8] },
  modal: { flex: 1, backgroundColor: colors.bg },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing[4],
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  modalTitle: { fontFamily: font.heading, fontSize: 20, color: colors.text },
  modalClose: { fontFamily: font.bodySemi, fontSize: 15, color: colors.primary },
  modalBody: { padding: spacing[4], gap: spacing[6] },
  section: { gap: spacing[2] },
  sectionLabel: {
    fontFamily: font.bodySemi,
    fontSize: 11,
    color: colors.textSub,
    letterSpacing: 1,
  },
  impactRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: spacing[1] },
  impactName: { fontFamily: font.bodyMed, fontSize: 14, color: colors.text },
  impactStats: { fontFamily: font.mono, fontSize: 13, color: colors.textSub },
  actions: { gap: spacing[3], marginTop: spacing[4] },
});
