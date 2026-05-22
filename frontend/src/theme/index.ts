export { colors } from './colors';

export const spacing = {
  1:  4,
  2:  8,
  3:  12,
  4:  16,
  6:  24,
  8:  32,
  12: 48,
  16: 64,
} as const;

export const radius = {
  sm:   4,
  md:   8,
  lg:   16,
  pill: 999,
} as const;

export const font = {
  heading: 'Syne_500Medium',
  body:    'DMSans_400Regular',
  bodyMed: 'DMSans_500Medium',
  bodySemi:'DMSans_600SemiBold',
  mono:    'JetBrainsMono_400Regular',
} as const;

export const shadow = {
  sm: {
    shadowColor:   '#000',
    shadowOffset:  { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius:  3,
    elevation:     2,
  },
  md: {
    shadowColor:   '#000',
    shadowOffset:  { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius:  16,
    elevation:     4,
  },
} as const;
