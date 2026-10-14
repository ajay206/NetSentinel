export function passwordProblems(password: string, username = ''): string[] {
  const problems: string[] = [];

  if (password.length < 10) problems.push('at least 10 characters');
  if (password.length > 128) problems.push('at most 128 characters');
  if (!/[a-z]/.test(password)) problems.push('a lowercase letter');
  if (!/[A-Z]/.test(password)) problems.push('an uppercase letter');
  if (!/[0-9]/.test(password)) problems.push('a digit');
  if (!/[^A-Za-z0-9]/.test(password)) problems.push('a symbol');
  if (username && password.toLowerCase().includes(username.toLowerCase())) {
    problems.push('must not contain the username');
  }

  return problems;
}

export function passwordStrength(password: string): 0 | 1 | 2 | 3 | 4 {
  if (!password) return 0;
  let score = 0;
  if (password.length >= 10) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  return score as 0 | 1 | 2 | 3 | 4;
}

export const STRENGTH_LABELS = ['Too weak', 'Weak', 'Fair', 'Good', 'Strong'] as const;
