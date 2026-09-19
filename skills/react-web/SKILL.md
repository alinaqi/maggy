---
name: react-web
description: React web development with hooks, React Query, Zustand
when-to-use: When working on React web components or pages
user-invocable: false
paths: ["**/*.tsx", "**/*.jsx", "src/components/**", "src/pages/**", "src/app/**"]
effort: medium
---

# React Web Skill


---

## Test-First Development (MANDATORY)

**CRITICAL: Tests MUST be written BEFORE implementation code. This is non-negotiable for frontend components.**

### The TFD Workflow

```
1. Write test file first → Defines expected behavior
2. Run test (it fails) → Confirms test is valid
3. Write minimal code → Just enough to pass
4. Run test (it passes) → Validates implementation
5. Refactor if needed → Tests catch regressions
```

### Component Development Order

```bash
# CORRECT ORDER - Test first
1. Create Button.test.tsx    # Write tests for expected behavior
2. Run tests (they fail)     # npm test -- Button
3. Create Button.tsx         # Implement to pass tests
4. Run tests (they pass)     # Verify implementation
5. Create Button.module.css  # Style after logic works

# WRONG ORDER - Never do this
1. Create Button.tsx         # ❌ No tests exist yet
2. Create Button.module.css  # ❌ Still no tests
3. "I'll add tests later"    # ❌ Tests never get written
```

### Test File Structure (Create First)

```typescript
// Button.test.tsx - CREATE THIS FIRST
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  // Define ALL expected behaviors upfront
  describe('rendering', () => {
    it('renders with label', () => {
      render(<Button label="Click me" onClick={() => {}} />);
      expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
    });

    it('applies variant class', () => {
      render(<Button label="Click" onClick={() => {}} variant="secondary" />);
      expect(screen.getByRole('button')).toHaveClass('secondary');
    });
  });

  describe('interactions', () => {
    it('calls onClick when clicked', () => {
      const onClick = vi.fn();
      render(<Button label="Click me" onClick={onClick} />);
      fireEvent.click(screen.getByRole('button'));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('does not call onClick when disabled', () => {
      const onClick = vi.fn();
      render(<Button label="Click me" onClick={onClick} disabled />);
      fireEvent.click(screen.getByRole('button'));
      expect(onClick).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has correct aria attributes when disabled', () => {
      render(<Button label="Click" onClick={() => {}} disabled />);
      expect(screen.getByRole('button')).toHaveAttribute('aria-disabled', 'true');
    });
  });
});
```

### Hook Test First Pattern

```typescript
// useCounter.test.ts - CREATE THIS FIRST
import { renderHook, act } from '@testing-library/react';
import { useCounter } from './useCounter';

describe('useCounter', () => {
  it('starts at initial value', () => {
    const { result } = renderHook(() => useCounter(5));
    expect(result.current.count).toBe(5);
  });

  it('increments', () => {
    const { result } = renderHook(() => useCounter());
    act(() => result.current.increment());
    expect(result.current.count).toBe(1);
  });

  it('decrements', () => {
    const { result } = renderHook(() => useCounter(5));
    act(() => result.current.decrement());
    expect(result.current.count).toBe(4);
  });

  it('resets to initial value', () => {
    const { result } = renderHook(() => useCounter(10));
    act(() => result.current.increment());
    act(() => result.current.reset());
    expect(result.current.count).toBe(10);
  });
});
```

### Enforcement Checklist

Before writing ANY component/hook implementation:

- [ ] Test file exists: `Component.test.tsx`
- [ ] All expected behaviors have test cases
- [ ] Tests run and FAIL (proves tests are valid)
- [ ] Only THEN create implementation file

**If tests are skipped, Claude MUST:**
```
⚠️ TEST-FIRST VIOLATION

Cannot create [Component].tsx - no test file exists.

Creating [Component].test.tsx first with tests for:
- Rendering with required props
- User interactions
- Edge cases
- Accessibility
```

---

## Project Structure

```
project/
├── src/
│   ├── core/                   # Pure business logic (no React)
│   │   ├── types.ts
│   │   └── services/
│   ├── components/             # Reusable UI components
│   │   ├── Button/
│   │   │   ├── Button.tsx
│   │   │   ├── Button.test.tsx
│   │   │   ├── Button.module.css  # or .styles.ts
│   │   │   └── index.ts
│   │   └── index.ts            # Barrel export
│   ├── pages/                  # Route-level components
│   │   ├── Home/
│   │   │   ├── HomePage.tsx
│   │   │   ├── useHome.ts      # Page-specific hook
│   │   │   └── index.ts
│   │   └── index.ts
│   ├── hooks/                  # Shared custom hooks
│   ├── store/                  # State management
│   ├── api/                    # API client and queries
│   ├── utils/                  # Utilities
│   ├── App.tsx
│   └── main.tsx
├── tests/
│   ├── unit/
│   └── e2e/
├── public/
├── package.json
├── tsconfig.json
├── vite.config.ts              # or next.config.js
└── CLAUDE.md
```

---

## Component Patterns

### Functional Components Only
```typescript
// Good - simple, testable
interface ButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary';
}

export function Button({
  label,
  onClick,
  disabled = false,
  variant = 'primary'
}: ButtonProps): JSX.Element {
  return (
    <button
      className={styles[variant]}
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </button>
  );
}
```

### Extract Logic to Hooks
```typescript
// useHome.ts - all logic here
export function useHome() {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    const data = await fetchItems();
    setItems(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { items, loading, refresh };
}

// HomePage.tsx - pure presentation
export function HomePage(): JSX.Element {
  const { items, loading, refresh } = useHome();

  if (loading) return <Spinner />;

  return <ItemList items={items} onRefresh={refresh} />;
}
```

### Props Interface Always Explicit
```typescript
// Always define props interface, even if simple
interface ItemCardProps {
  item: Item;
  onClick: (id: string) => void;
}

export function ItemCard({ item, onClick }: ItemCardProps): JSX.Element {
  return (
    <div onClick={() => onClick(item.id)}>
      <h3>{item.title}</h3>
    </div>
  );
}
```

---

## State Management

### Local State First
```typescript
// Start with useState, escalate only when needed
const [value, setValue] = useState('');
```

### Zustand for Global State (if needed)
```typescript
// store/useAppStore.ts
import { create } from 'zustand';

interface AppState {
  user: User | null;
  theme: 'light' | 'dark';
  setUser: (user: User | null) => void;
  toggleTheme: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  theme: 'light',
  setUser: (user) => set({ user }),
  toggleTheme: () => set((state) => ({
    theme: state.theme === 'light' ? 'dark' : 'light'
  })),
}));
```

### React Query for Server State
```typescript
// api/queries/useItems.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { itemsApi } from '../client';

export function useItems() {
  return useQuery({
    queryKey: ['items'],
    queryFn: itemsApi.getAll,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useCreateItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: itemsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
    },
  });
}
```

---

## Routing

### React Router (Vite/CRA)
```typescript
// App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';

export function App(): JSX.Element {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/items/:id" element={<ItemPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
```

### Protected Routes
```typescript
interface ProtectedRouteProps {
  children: JSX.Element;
}

function ProtectedRoute({ children }: ProtectedRouteProps): JSX.Element {
  const { user } = useAppStore();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
```

---

## Styling

### CSS Modules (Preferred)
```typescript
// Button.module.css
.primary {
  background: var(--color-primary);
  color: white;
}

.secondary {
  background: transparent;
  border: 1px solid var(--color-primary);
}

// Button.tsx
import styles from './Button.module.css';

<button className={styles.primary}>Click</button>
```

### Tailwind (Alternative)
```typescript
// Use consistent patterns, extract repeated combinations
const buttonVariants = {
  primary: 'bg-blue-500 text-white hover:bg-blue-600',
  secondary: 'bg-transparent border border-blue-500 text-blue-500',
} as const;

<button className={buttonVariants[variant]}>{label}</button>
```

---

## Forms

### React Hook Form + Zod
```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

type FormData = z.infer<typeof schema>;

export function LoginForm(): JSX.Element {
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = (data: FormData) => {
    // handle submit
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('email')} />
      {errors.email && <span>{errors.email.message}</span>}

      <input type="password" {...register('password')} />
      {errors.password && <span>{errors.password.message}</span>}

      <button type="submit">Login</button>
    </form>
  );
}
```

---

## Testing

### Component Testing with React Testing Library
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(<Button label="Click me" onClick={onClick} />);

    fireEvent.click(screen.getByText('Click me'));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('does not call onClick when disabled', () => {
    const onClick = vi.fn();
    render(<Button label="Click me" onClick={onClick} disabled />);

    fireEvent.click(screen.getByText('Click me'));

    expect(onClick).not.toHaveBeenCalled();
  });

  it('applies correct variant class', () => {
    render(<Button label="Click" onClick={() => {}} variant="secondary" />);

    expect(screen.getByRole('button')).toHaveClass('secondary');
  });
});
```

### Hook Testing
```typescript
import { renderHook, act, waitFor } from '@testing-library/react';
import { useCounter } from './useCounter';

describe('useCounter', () => {
  it('increments counter', () => {
    const { result } = renderHook(() => useCounter());

    act(() => {
      result.current.increment();
    });

    expect(result.current.count).toBe(1);
  });
});
```

### E2E with Playwright
```typescript
// tests/e2e/login.spec.ts
import { test, expect } from '@playwright/test';

test('user can login', async ({ page }) => {
  await page.goto('/login');

  await page.fill('[name="email"]', 'test@example.com');
  await page.fill('[name="password"]', 'password123');
  await page.click('button[type="submit"]');

  await expect(page).toHaveURL('/dashboard');
  await expect(page.getByText('Welcome')).toBeVisible();
});
```

### Visual validation (default for web)

Behavior tests prove logic; they don't prove the UI actually *looks* and *flows*
right. For any user-facing flow, close the loop visually before calling it done:

- **`demo-video`** (default) — a captioned Playwright walkthrough that records the
  real flow, doubles as a passing E2E test, and produces a stakeholder proof mp4.
  This is the harness's default visual validation for web work; a user-facing flow
  isn't "done" without it (see the Definition of Done in `base`).
- **`visual-validation`** — autonomous screenshot-regression checks for pixel-level
  UI changes.

Together: `playwright-testing` proves behavior, `visual-validation` catches visual
regressions, `demo-video` proves the whole flow the way a person sees it.

---

## Performance

### Memoization
```typescript
// Memoize expensive components
const ItemList = memo(function ItemList({ items }: ItemListProps) {
  return items.map(item => <ItemCard key={item.id} item={item} />);
});

// Memoize callbacks passed to children
const handleClick = useCallback((id: string) => {
  setSelectedId(id);
}, []);

// Memoize expensive computations
const sortedItems = useMemo(() => {
  return [...items].sort((a, b) => a.name.localeCompare(b.name));
}, [items]);
```

### Code Splitting
```typescript
// Lazy load routes
const ItemPage = lazy(() => import('./pages/Item'));

<Suspense fallback={<Spinner />}>
  <Route path="/items/:id" element={<ItemPage />} />
</Suspense>
```

---

## React Web Anti-Patterns

- ❌ Inline functions in JSX - use useCallback
- ❌ Logic in render - extract to hooks
- ❌ Deep component nesting - flatten hierarchy
- ❌ Index as key in lists - use stable IDs
- ❌ Direct state mutation - always use setter
- ❌ Prop drilling > 2 levels - use context or state management
- ❌ useEffect for derived state - use useMemo
- ❌ Fetching in useEffect - use React Query
- ❌ Mixing business logic with UI - keep core/ pure
- ❌ Large components (>100 lines) - split into smaller pieces
- ❌ CSS in JS objects - use CSS modules or Tailwind
- ❌ Ignoring TypeScript errors - fix them
