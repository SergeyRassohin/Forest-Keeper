import security from 'eslint-plugin-security';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  ...tseslint.configs.recommended,
  security.configs.recommended,
);
