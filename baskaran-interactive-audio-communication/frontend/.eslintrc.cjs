module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: {jsx:true}},
  plugins: ['@typescript-eslint'],
  env: {browser:true, node:true, es2022:true},
  extends: ['eslint:recommended'],
  rules: {'no-unused-vars':'off','no-undef':'off','no-extra-semi':'off'},
};
