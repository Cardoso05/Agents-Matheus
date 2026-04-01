ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE debts ENABLE ROW LEVEL SECURITY;
ALTER TABLE debt_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE open_finance_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can CRUD own accounts" ON accounts FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own transactions" ON transactions FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can view global and own categories" ON categories
  FOR SELECT USING (user_id IS NULL OR auth.uid() = user_id);
CREATE POLICY "Users can CRUD own categories" ON categories
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own rules" ON category_rules FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own debts" ON debts FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own debt payments" ON debt_payments
  FOR ALL USING (
    EXISTS (SELECT 1 FROM debts WHERE debts.id = debt_payments.debt_id AND debts.user_id = auth.uid())
  );

CREATE POLICY "Users can CRUD own reports" ON reports FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own alerts" ON alerts FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own connections" ON open_finance_connections FOR ALL USING (auth.uid() = user_id);
