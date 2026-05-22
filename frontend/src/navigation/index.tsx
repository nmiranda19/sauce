import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createStackNavigator } from '@react-navigation/stack';
import { Home, Users, ArrowLeftRight, Trophy, Gavel } from 'lucide-react-native';

import { HomeScreen } from '@/screens/HomeScreen';
import { LineupScreen } from '@/screens/LineupScreen';
import { MatchupScreen } from '@/screens/MatchupScreen';
import { StandingsScreen } from '@/screens/StandingsScreen';
import { WaiverScreen } from '@/screens/WaiverScreen';
import { TradesScreen } from '@/screens/TradesScreen';
import { CommissionerScreen } from '@/screens/CommissionerScreen';
import { LoginScreen } from '@/screens/LoginScreen';
import { useAuthStore } from '@/store/auth';
import { colors, font } from '@/theme';

const Tab = createBottomTabNavigator();
const Stack = createStackNavigator();

const TAB_ICON_SIZE = 24;
const ICON_STROKE = 1.75;

function MainTabs({ isCommissioner }: { isCommissioner: boolean }) {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.card, shadowColor: 'transparent', elevation: 0 },
        headerTitleStyle: { fontFamily: font.heading, fontSize: 20, color: colors.text },
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          paddingBottom: 4,
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textSub,
        tabBarLabelStyle: { fontFamily: font.body, fontSize: 11 },
      })}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          title: 'Sauce',
          tabBarIcon: ({ color }) => <Home size={TAB_ICON_SIZE} color={color} strokeWidth={ICON_STROKE} />,
        }}
      />
      <Tab.Screen
        name="Lineup"
        component={LineupScreen}
        options={{
          tabBarIcon: ({ color }) => <Users size={TAB_ICON_SIZE} color={color} strokeWidth={ICON_STROKE} />,
        }}
      />
      <Tab.Screen
        name="Matchup"
        component={MatchupScreen}
        options={{
          title: 'Matchup',
          tabBarIcon: ({ color }) => <Trophy size={TAB_ICON_SIZE} color={color} strokeWidth={ICON_STROKE} />,
        }}
      />
      <Tab.Screen
        name="Standings"
        component={StandingsScreen}
        options={{
          tabBarIcon: ({ color }) => (
            <ArrowLeftRight size={TAB_ICON_SIZE} color={color} strokeWidth={ICON_STROKE} />
          ),
        }}
      />
      <Tab.Screen
        name="Waivers"
        component={WaiverScreen}
        options={{
          tabBarIcon: ({ color }) => (
            <ArrowLeftRight size={TAB_ICON_SIZE} color={color} strokeWidth={ICON_STROKE} />
          ),
        }}
      />
      <Tab.Screen
        name="Trades"
        component={TradesScreen}
        options={{
          tabBarIcon: ({ color }) => (
            <ArrowLeftRight size={TAB_ICON_SIZE} color={color} strokeWidth={ICON_STROKE} />
          ),
        }}
      />
      {isCommissioner && (
        <Tab.Screen
          name="Commissioner"
          component={CommissionerScreen}
          options={{
            tabBarIcon: ({ color }) => <Gavel size={TAB_ICON_SIZE} color={color} strokeWidth={ICON_STROKE} />,
          }}
        />
      )}
    </Tab.Navigator>
  );
}

export function AppNavigator() {
  const { user } = useAuthStore();

  if (!user) {
    return (
      <NavigationContainer>
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          <Stack.Screen name="Login" component={LoginScreen} />
        </Stack.Navigator>
      </NavigationContainer>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        <Stack.Screen name="Main">
          {() => <MainTabs isCommissioner={user.is_commissioner} />}
        </Stack.Screen>
      </Stack.Navigator>
    </NavigationContainer>
  );
}
