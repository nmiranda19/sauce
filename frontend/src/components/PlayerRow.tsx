import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors, font, spacing } from '@/theme';

interface Player {
  id: string;
  full_name: string;
  position: string;
  nhl_team?: string;
  status?: string;
  slot?: string;
  fantasy_points?: number;
  games_remaining?: number;
}

interface Props {
  player: Player;
  onPress?: () => void;
  right?: React.ReactNode;
  showSlot?: boolean;
  showGames?: boolean;
}

function statusColor(status?: string) {
  if (!status || status === 'Active') return colors.active;
  if (status === 'IR' || status === 'IR-LT') return colors.ir;
  if (status === 'DTD') return colors.dtd;
  if (status === 'OUT') return colors.loss;
  return colors.textDim;
}

export function PlayerRow({ player, onPress, right, showSlot, showGames }: Props) {
  const content = (
    <View style={styles.row}>
      <View style={styles.left}>
        {showSlot && (
          <Text style={styles.slot}>{player.slot ?? player.position}</Text>
        )}
        {!showSlot && (
          <View style={styles.posTag}>
            <Text style={styles.pos}>{player.position}</Text>
          </View>
        )}
        <View style={styles.info}>
          <Text style={styles.name} numberOfLines={1}>{player.full_name}</Text>
          <View style={styles.meta}>
            {player.nhl_team && (
              <Text style={styles.metaText}>{player.nhl_team}</Text>
            )}
            {player.status && player.status !== 'Active' && (
              <Text style={[styles.statusBadge, { color: statusColor(player.status) }]}>
                {player.status}
              </Text>
            )}
            {showGames && player.games_remaining !== undefined && (
              <Text style={styles.metaText}>{player.games_remaining}GP left</Text>
            )}
          </View>
        </View>
      </View>
      {right && <View style={styles.right}>{right}</View>}
    </View>
  );

  if (onPress) {
    return (
      <TouchableOpacity onPress={onPress} activeOpacity={0.7}>
        {content}
      </TouchableOpacity>
    );
  }
  return content;
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing[2],
    gap: spacing[3],
  },
  left: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[3],
  },
  slot: {
    fontFamily: font.bodySemi,
    fontSize: 12,
    color: colors.primary,
    width: 32,
    textAlign: 'center',
  },
  posTag: {
    backgroundColor: colors.surface,
    borderRadius: 4,
    paddingHorizontal: spacing[2],
    paddingVertical: 2,
    minWidth: 32,
    alignItems: 'center',
  },
  pos: {
    fontFamily: font.mono,
    fontSize: 11,
    color: colors.textSub,
  },
  info: {
    flex: 1,
    gap: 2,
  },
  name: {
    fontFamily: font.bodyMed,
    fontSize: 15,
    color: colors.text,
  },
  meta: {
    flexDirection: 'row',
    gap: spacing[2],
    alignItems: 'center',
  },
  metaText: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.textSub,
  },
  statusBadge: {
    fontFamily: font.bodySemi,
    fontSize: 11,
  },
  right: {
    alignItems: 'flex-end',
  },
});
