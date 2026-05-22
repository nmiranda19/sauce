import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  TouchableOpacity,
  ScrollView,
  Alert,
} from 'react-native';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/Button';
import { colors, font, spacing, radius } from '@/theme';

export function LoginScreen() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { login, register, loading } = useAuthStore();

  async function submit() {
    try {
      if (mode === 'login') {
        await login(email.trim(), password);
      } else {
        if (!name.trim()) { Alert.alert('Name required'); return; }
        await register(name.trim(), email.trim(), password);
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Something went wrong. Try again?';
      Alert.alert('Error', msg);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.header}>
          <Text style={styles.wordmark}>SAUCE</Text>
          <Text style={styles.tagline}>Your league. Your rules.</Text>
        </View>

        <View style={styles.form}>
          {mode === 'register' && (
            <TextInput
              style={styles.input}
              placeholder="Name"
              placeholderTextColor={colors.textDim}
              value={name}
              onChangeText={setName}
              autoCapitalize="words"
              autoCorrect={false}
            />
          )}
          <TextInput
            style={styles.input}
            placeholder="Email"
            placeholderTextColor={colors.textDim}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TextInput
            style={styles.input}
            placeholder="Password"
            placeholderTextColor={colors.textDim}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />

          <Button
            label={mode === 'login' ? "Let's go" : 'Create account'}
            onPress={submit}
            loading={loading}
            style={styles.submitBtn}
          />
        </View>

        <TouchableOpacity onPress={() => setMode(mode === 'login' ? 'register' : 'login')}>
          <Text style={styles.toggle}>
            {mode === 'login' ? 'New here? Sign up' : 'Already have an account? Sign in'}
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.bg },
  container: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing[6],
    paddingVertical: spacing[12],
    gap: spacing[8],
  },
  header: {
    alignItems: 'center',
    gap: spacing[2],
  },
  wordmark: {
    fontFamily: font.heading,
    fontSize: 48,
    color: colors.text,
    letterSpacing: -2,
  },
  tagline: {
    fontFamily: font.body,
    fontSize: 16,
    color: colors.textSub,
  },
  form: {
    gap: spacing[3],
  },
  input: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing[4],
    paddingVertical: spacing[3],
    fontFamily: font.body,
    fontSize: 16,
    color: colors.text,
    height: 52,
  },
  submitBtn: {
    marginTop: spacing[2],
  },
  toggle: {
    fontFamily: font.body,
    fontSize: 14,
    color: colors.primary,
    textAlign: 'center',
  },
});
