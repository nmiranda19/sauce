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
  TextInput,
} from 'react-native';
import { waiverApi, playerApi, teamApi } from '@/api/endpoints';
import { PlayerRow } from '@/components/PlayerRow';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { Spinner } from '@/components/Spinner';
import { colors, font, spacing, radius } from '@/theme';

const POSITIONS = ['', 'C', 'LW', 'RW', 'D', 'G'];

export function WaiverScreen() {
  const [tab, setTab] = useState<'available' | 'claims'>('available');
  const [players, setPlayers] = useState<any[]>([]);
  const [claims, setClaims] = useState<any[]>([]);
  const [roster, setRoster] = useState<any[]>([]);
  const [priority, setPriority] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [posFilter, setPosFilter] = useState('');
  const [searchQ, setSearchQ] = useState('');
  const [claimModal, setClaimModal] = useState<any | null>(null);
  const [selectedSlot, setSelectedSlot] = useState('');
  const [dropPlayer, setDropPlayer] = useState<any | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      const [playersRes, claimsRes, rosterRes, priorityRes] = await Promise.allSettled([
        playerApi.available(searchQ, posFilter),
        waiverApi.myClaims(),
        teamApi.myRoster(),
        waiverApi.priority(),
      ]);
      if (playersRes.status === 'fulfilled') setPlayers(playersRes.value.data);
      if (claimsRes.status === 'fulfilled') setClaims(claimsRes.value.data);
      if (rosterRes.status === 'fulfilled') setRoster(rosterRes.value.data);
      if (priorityRes.status === 'fulfilled') {
        const pData = priorityRes.value.data;
        const myEntry = Array.isArray(pData) ? pData.find((p: any) => p.is_mine) : null;
        if (myEntry) setPriority(myEntry.priority);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [searchQ, posFilter]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  async function submitClaim() {
    if (!claimModal || !selectedSlot) {
      Alert.alert('Select a slot first');
      return;
    }
    setSubmitting(true);
    try {
      await waiverApi.claim(claimModal.id, selectedSlot, dropPlayer?.id);
      setClaimModal(null);
      setDropPlayer(null);
      setSelectedSlot('');
      load();
      Alert.alert('Claim submitted', 'Your waiver claim has been queued.');
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail ?? 'Could not submit claim.');
    } finally {
      setSubmitting(false);
    }
  }

  async function dropFromRoster(player: any) {
    Alert.alert(
      `Drop ${player.full_name}?`,
      'This player will go to waivers for 24 hours.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Drop',
          style: 'destructive',
          onPress: async () => {
            try {
              await waiverApi.drop(player.id);
              load();
            } catch (e: any) {
              Alert.alert('Error', e?.response?.data?.detail ?? 'Could not drop player.');
            }
          },
        },
      ]
    );
  }

  if (loading) return <Spinner fullscreen />;

  return (
    <View style={styles.container}>
      {/* Tabs */}
      <View style={styles.tabs}>
        {(['available', 'claims'] as const).map((t) => (
          <TouchableOpacity
            key={t}
            style={[styles.tab, tab === t && styles.tabActive]}
            onPress={() => setTab(t)}
          >
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === 'available' ? 'Available' : `My Claims${claims.length ? ` (${claims.length})` : ''}`}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {priority !== null && (
        <Text style={styles.priority}>Waiver priority: #{priority}</Text>
      )}

      {tab === 'available' && (
        <>
          <TextInput
            style={styles.search}
            placeholder="Search players..."
            placeholderTextColor={colors.textDim}
            value={searchQ}
            onChangeText={setSearchQ}
          />
          <View style={styles.posFilters}>
            {POSITIONS.map((pos) => (
              <TouchableOpacity
                key={pos || 'ALL'}
                style={[styles.posBtn, posFilter === pos && styles.posBtnActive]}
                onPress={() => setPosFilter(pos)}
              >
                <Text style={[styles.posBtnText, posFilter === pos && styles.posBtnTextActive]}>
                  {pos || 'ALL'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <FlatList
            data={players}
            keyExtractor={(item) => item.id}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
            contentContainerStyle={styles.list}
            renderItem={({ item }) => (
              <Card style={styles.playerCard}>
                <PlayerRow
                  player={item}
                  right={
                    <Button
                      label="Claim"
                      onPress={() => setClaimModal(item)}
                      style={styles.claimBtn}
                    />
                  }
                />
              </Card>
            )}
          />
        </>
      )}

      {tab === 'claims' && (
        <FlatList
          data={claims}
          keyExtractor={(item) => item.id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <Card style={styles.playerCard}>
              <Text style={styles.claimStatus}>{item.status}</Text>
              <Text style={styles.claimDetail}>Add: {item.player_to_add?.full_name}</Text>
              {item.player_to_drop && (
                <Text style={styles.claimDetail}>Drop: {item.player_to_drop?.full_name}</Text>
              )}
            </Card>
          )}
          ListEmptyComponent={
            <Text style={styles.empty}>No active claims.</Text>
          }
        />
      )}

      {/* Claim modal */}
      <Modal visible={!!claimModal} animationType="slide" presentationStyle="pageSheet">
        <View style={styles.modal}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Claim {claimModal?.full_name}</Text>
            <TouchableOpacity onPress={() => { setClaimModal(null); setDropPlayer(null); setSelectedSlot(''); }}>
              <Text style={styles.modalClose}>Cancel</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.modalBody}>
            <Text style={styles.fieldLabel}>Target slot</Text>
            <View style={styles.slotRow}>
              {['C','LW','RW','D','UTIL','G','BN'].map(s => (
                <TouchableOpacity
                  key={s}
                  style={[styles.slotBtn, selectedSlot === s && styles.slotBtnActive]}
                  onPress={() => setSelectedSlot(s)}
                >
                  <Text style={[styles.slotBtnText, selectedSlot === s && styles.slotBtnTextActive]}>{s}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.fieldLabel}>Drop player (optional)</Text>
            <FlatList
              data={roster.filter(p => p.slot !== 'IR')}
              keyExtractor={(item) => item.id}
              style={styles.dropList}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[styles.dropRow, dropPlayer?.id === item.id && styles.dropRowActive]}
                  onPress={() => setDropPlayer(dropPlayer?.id === item.id ? null : item)}
                >
                  <Text style={styles.dropName}>{item.full_name}</Text>
                  <Text style={styles.dropSlot}>{item.slot}</Text>
                </TouchableOpacity>
              )}
            />

            <Button
              label="Submit Claim"
              onPress={submitClaim}
              loading={submitting}
              style={styles.submitBtn}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  tabs: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.card,
  },
  tab: {
    flex: 1,
    paddingVertical: spacing[3],
    alignItems: 'center',
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: colors.primary,
  },
  tabText: {
    fontFamily: font.bodyMed,
    fontSize: 14,
    color: colors.textSub,
  },
  tabTextActive: { color: colors.primary },
  priority: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.textSub,
    textAlign: 'center',
    paddingVertical: spacing[2],
    backgroundColor: colors.surface,
  },
  search: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing[4],
    paddingVertical: spacing[2],
    fontFamily: font.body,
    fontSize: 15,
    color: colors.text,
    margin: spacing[4],
    marginBottom: spacing[2],
    height: 44,
  },
  posFilters: {
    flexDirection: 'row',
    gap: spacing[2],
    paddingHorizontal: spacing[4],
    marginBottom: spacing[3],
  },
  posBtn: {
    paddingHorizontal: spacing[3],
    paddingVertical: spacing[1],
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  posBtnActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  posBtnText: {
    fontFamily: font.bodySemi,
    fontSize: 12,
    color: colors.textSub,
  },
  posBtnTextActive: { color: '#fff' },
  list: { padding: spacing[4], gap: spacing[2] },
  playerCard: { padding: spacing[3] },
  claimBtn: {
    paddingHorizontal: spacing[3],
    paddingVertical: 6,
    minHeight: 36,
  },
  claimStatus: {
    fontFamily: font.bodySemi,
    fontSize: 12,
    color: colors.primary,
    textTransform: 'capitalize',
  },
  claimDetail: {
    fontFamily: font.body,
    fontSize: 14,
    color: colors.text,
  },
  empty: {
    fontFamily: font.body,
    fontSize: 15,
    color: colors.textSub,
    textAlign: 'center',
    marginTop: spacing[8],
  },
  modal: { flex: 1, backgroundColor: colors.bg },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing[4],
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  modalTitle: {
    fontFamily: font.heading,
    fontSize: 18,
    color: colors.text,
    flex: 1,
  },
  modalClose: {
    fontFamily: font.bodySemi,
    fontSize: 15,
    color: colors.loss,
  },
  modalBody: { padding: spacing[4], gap: spacing[4] },
  fieldLabel: {
    fontFamily: font.bodySemi,
    fontSize: 13,
    color: colors.textSub,
    letterSpacing: 0.5,
  },
  slotRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing[2] },
  slotBtn: {
    paddingHorizontal: spacing[3],
    paddingVertical: spacing[2],
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  slotBtnActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  slotBtnText: { fontFamily: font.bodySemi, fontSize: 13, color: colors.textSub },
  slotBtnTextActive: { color: '#fff' },
  dropList: { maxHeight: 220 },
  dropRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing[3],
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  dropRowActive: { backgroundColor: colors.primaryMuted + '44' },
  dropName: { fontFamily: font.bodyMed, fontSize: 14, color: colors.text },
  dropSlot: { fontFamily: font.mono, fontSize: 13, color: colors.textSub },
  submitBtn: { marginTop: spacing[4] },
});
