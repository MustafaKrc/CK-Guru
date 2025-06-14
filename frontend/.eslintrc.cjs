/**  .eslintrc.cjs
 *   Opinionated ESLint + Prettier config for
 *   Next.js 15, React 18, TypeScript 5, Tailwind.
 */
module.exports = {
  root: true,

  // --- Parsing -------------------------------------------------------------
  parser: '@typescript-eslint/parser',
  parserOptions: {
    project: './tsconfig.json',        // enables type-aware lint rules
    ecmaVersion: 'latest',
    sourceType: 'module',
  },

  // --- Plugins -------------------------------------------------------------
  plugins: [
    '@typescript-eslint',
    'react',
    'react-hooks',
    'jsx-a11y',
    'prettier',
  ],

  // --- Shareable rule sets -------------------------------------------------
  extends: [
    /* Core */
    'eslint:recommended',

    /* TypeScript */
    'plugin:@typescript-eslint/recommended',
    'plugin:@typescript-eslint/recommended-requiring-type-checking',

    /* React + Next */
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
    'plugin:jsx-a11y/recommended',
    'plugin:@next/next/core-web-vitals',

    /* Code-style handled by Prettier (last!) */
    'plugin:prettier/recommended',
  ],

  // --- Rule tweaks ---------------------------------------------------------
  rules: {
    /* React 17+ doesn’t need React in scope */
    'react/react-in-jsx-scope': 'off',

    /* Ignore unused args prefixed with _  */
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],

    /* Let Prettier be the single source of formatting truth */
    'prettier/prettier': [
      'error',
      {
        endOfLine: 'auto',
      },
    ],
  },

  // --- Env / globals -------------------------------------------------------
  settings: {
    react: { version: 'detect' },
    next:  { rootDir: ['apps/*/', './'] },  // monorepo-friendly
  },

  /* Files to ignore (in addition to .eslintignore) */
  ignorePatterns: [
    '.next/',
    'node_modules/',
    'dist/',
    'build/',
  ],
};
