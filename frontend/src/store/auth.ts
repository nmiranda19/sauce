import { create } from 'zustand';
import { saveToken, clearToken } from '@/api/client';
import { authApi } from '@/api/endpoints';

interface User {
  id: string;
  name: string;
  email: string;
  is_commissioner: boolean;
}

interface AuthStore {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  loading: false,

  login: async (email, password) => {
    set({ loading: true });
    try {
      const res = await authApi.login(email, password);
      await saveToken(res.data.access_token);
      const me = await authApi.me();
      set({ user: me.data, loading: false });
    } catch (e) {
      set({ loading: false });
      throw e;
    }
  },

  register: async (name, email, password) => {
    set({ loading: true });
    try {
      await authApi.register(name, email, password);
      const res = await authApi.login(email, password);
      await saveToken(res.data.access_token);
      const me = await authApi.me();
      set({ user: me.data, loading: false });
    } catch (e) {
      set({ loading: false });
      throw e;
    }
  },

  logout: async () => {
    await clearToken();
    set({ user: null });
  },

  fetchMe: async () => {
    try {
      const me = await authApi.me();
      set({ user: me.data });
    } catch {
      set({ user: null });
    }
  },
}));
