import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SectionList,
  RefreshControl,
  TouchableOpacity,
  Alert,
  Modal,
  FlatList,
  TextInput,
} from 'react-native';
import { teamApi, lineupApi, playerApi } from '@/api/endpoints';
import { PlayerRow } from '@/components/PlayerRow';
import { Button } from '@/components/Button';
import { Spinner } from '@/components/Spinner';
import { Card } from '@/components/Card';
import { colors, font, spacing, radius } from '@/theme';

const SLOT_ORDER = ['C', 'LW', 'RW', 'D', 'D', 'UTIL', 'G', 'G', 'G', 'IR', 'IR', 'IR', 'BN'];

interface RosterPlayer {
  id: string;
  full_name: string;
  position: string;
  nhl_team: string;
  status: string;
  slot: string;
  games_remaining_this_week?: number;
}

export function LineupScreen() {
  const [roster, setRoster] = useState<RosterPlayer[]>([]);
  const [locked, setLocked] = useState(false);
  const [lockTime, setLockTime] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [swapSource, setSwapSource] = useState<RosterPlayer | null>(null);
  const [searchVisible, setSearchVisible] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  const load = useCallback(async () => {
    try {
      const [rosterRes, lockRes] = await Promise.all([
        teamApi.myRoster(),
        lineupApi.lockStatus(),
      ]);
      setRoster(rosterRes.data);
      setLocked(lockRes.data.locked);
      setLockTime(lockRes.data.lock_time ?? null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  async function handleSwap(target: RosterPlayer) {
    if (!swapSource) return;
    try {
      await lineupApi.swapSlot(swapSource.id, target.slot);
      setSwapSource(null);
      load();
    } catch (e: any) {
      Alert.alert('Swap failed', e?.response?.data?.detail ?? 'Could not swap players.');
      setSwapSource(null);
    }
  }

  async function doSearch(q: string) {
    setSearchQ(q);
    if (q.length < 2) { setSearchResults([]); return; }
    setSearching(true);
    try {
      const res = await playerApi.available(q);
      setSearchResults(res.data);
    } finally {
      setSearching(false);
    }
  }

  const sections = [
    { title: 'Active', data: roster.filter(p => !['BN','IR'].includes(p.slot)) },
    { title: 'Bench', data: roster.filter(p => p.slot === 'BN') },
    { title: 'IR', data: roster.filter(p => p.slot === 'IR') },
  ].filter(s => s.data.length > 0);

  if (loading) return <Spinner fullscreen />;

  return (
    <View style={styles.container}>
      {/* Lock banner */}
      {locked && (
        <View style={styles.lockBanner}>
          <Text style={styles.lockText}>Lineup locked — games in progress</Text>
        </View>
      )}
      {!locked && lockTime && (
        <View style={styles.unlockBanner}>
          <Text style={styles.unlockText}>
            Locks at {new Date(lockTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </Text>
        </View>
      )}

      {swapSource && (
        <View style={styles.swapBanner}>
          <Text style={styles.swapText}>Select destination for {swapSource.full_name}</Text>
          <TouchableOpacity onPress={() => setSwapSource(null)}>
            <Text style={styles.swapCancel}>Cancel</Text>
          </TouchableOpacity>
        </View>
      )}

      <SectionList
        sections={sections}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
        contentContainerStyle={styles.list}
        renderSectionHeader={({ section }) => (
          <Text style={styles.sectionHeader}>{section.title}</Text>
        )}
        renderItem={({ item }) => {
          const isSwapSrc = swapSource?.id === item.id;
          return (
            <TouchableOpacity
              onPress={() => {
                if (locked) return;
                if (swapSource) {
                  handleSwap(item);
                } else {
                  setSwapSource(item);
                }
              }}
              activeOpacity={locked ? 1 : 0.7}
              style={[styles.playerCard, isSwapSrc && styles.swapSrcCard]}
            >
              <PlayerRow
                player={item}
                showSlot
                showGames
                right={
                  !locked && !swapSource ? (
                    <Text style={styles.swapHint}>Swap</Text>
                  ) : swapSource && !isSwapSrc ? (
                    <Text style={styles.moveHere}>Move here</Text>
                  ) : undefined
                }
              />
            </TouchableOpacity>
          );
        }}
        ListFooterComponent={
          <Button
            label="Add Player"
            variant="secondary"
            onPress={() => setSearchVisible(true)}
            style={styles.addBtn}
          />
        }
      />

      {/* Add player modal */}
      <Modal visible={searchVisible} animationType="slide" presentationStyle="pageSheet">
        <View style={styles.modal}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Add Player</Text>
            <TouchableOpacity onPress={() => { setSearchVisible(false); setSearchQ(''); setSearchResults([]); }}>
              <Text style={styles.modalClose}>Done</Text>
            </TouchableOpacity>
          </View>
          <TextInput
            style={styles.searchInput}
            placeholder="Search players..."
            placeholderTextColor={colors.textDim}
            value={searchQ}
            onChangeText={doSearch}
            autoFocus
          />
          {searching && <Spinner />}
          <FlatList
            data={searchResults}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => (
              <Card style={styles.searchCard}>
                <PlayerRow
                  player={item}
                  right={
                    <Button
                      label="Add"
                      onPress={() => {
                        setSearchVisible(false);
                      }}
                      style={styles.addSmall}
                    />
                  }
                />
              </Card>
            )}
            contentContainerStyle={{ padding: spacing[4], gap: spacing[2] }}
          />
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { padding: spacing[4], gap: spacing[2] },
  sectionHeader: {
    fontFamily: font.bodySemi,
    fontSize: 11,
    color: colors.textSub,
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginTop: spacing[4],
    marginBottom: spacing[2],
  },
  playerCard: {
    backgroundColor: colors.card,
    borderRadius: radius.md,
    paddingHorizontal: spacing[4],
    paddingVertical: spacing[2],
    borderWidth: 1,
    borderColor: colors.border,
  },
  swapSrcCard: {
    borderColor: colors.primary,
    borderWidth: 2,
  },
  swapHint: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.textDim,
  },
  moveHere: {
    fontFamily: font.bodySemi,
    fontSize: 12,
    color: colors.primary,
  },
  lockBanner: {
    backgroundColor: colors.loss,
    padding: spacing[3],
    alignItems: 'center',
  },
  lockText: {
    fontFamily: font.bodySemi,
    fontSize: 13,
    color: '#fff',
  },
  unlockBanner: {
    backgroundColor: colors.primaryMuted,
    padding: spacing[2],
    alignItems: 'center',
  },
  unlockText: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.primaryDark,
  },
  swapBanner: {
    backgroundColor: colors.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing[3],
    paddingHorizontal: spacing[4],
  },
  swapText: {
    fontFamily: font.bodyMed,
    fontSize: 13,
    color: '#fff',
    flex: 1,
  },
  swapCancel: {
    fontFamily: font.bodySemi,
    fontSize: 13,
    color: '#fff',
  },
  addBtn: { marginTop: spacing[4] },
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
    fontSize: 20,
    color: colors.text,
  },
  modalClose: {
    fontFamily: font.bodySemi,
    fontSize: 15,
    color: colors.primary,
  },
  searchInput: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing[4],
    paddingVertical: spacing[3],
    fontFamily: font.body,
    fontSize: 16,
    color: colors.text,
    margin: spacing[4],
    height: 48,
  },
  searchCard: { padding: spacing[3] },
  addSmall: {
    paddingHorizontal: spacing[3],
    paddingVertical: 6,
    minHeight: 36,
  },
});
