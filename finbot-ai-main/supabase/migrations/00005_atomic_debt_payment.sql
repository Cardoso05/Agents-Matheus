-- Atomic debt payment: insert payment + update balance in a single transaction
-- Prevents inconsistent state if one operation fails

CREATE OR REPLACE FUNCTION record_debt_payment(
  p_debt_id UUID,
  p_user_id UUID,
  p_date DATE,
  p_amount DECIMAL(12,2),
  p_is_extra BOOLEAN DEFAULT FALSE,
  p_notes TEXT DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
  v_old_balance DECIMAL(12,2);
  v_new_balance DECIMAL(12,2);
  v_debt_name TEXT;
  v_payment_id UUID;
BEGIN
  -- Verify debt belongs to user and get current state (row lock)
  SELECT current_balance, name INTO v_old_balance, v_debt_name
  FROM debts
  WHERE id = p_debt_id
    AND user_id = p_user_id
    AND status = 'active'
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Debt not found, not owned by user, or already paid off';
  END IF;

  -- Calculate new balance
  v_new_balance := GREATEST(0, v_old_balance - p_amount);

  -- Insert payment record
  INSERT INTO debt_payments (debt_id, date, amount, is_extra, notes)
  VALUES (p_debt_id, p_date, p_amount, p_is_extra, p_notes)
  RETURNING id INTO v_payment_id;

  -- Update debt balance and status atomically
  UPDATE debts
  SET current_balance = v_new_balance,
      status = CASE WHEN v_new_balance <= 0 THEN 'paid_off'::debt_status ELSE status END
  WHERE id = p_debt_id;

  RETURN jsonb_build_object(
    'payment_id', v_payment_id,
    'old_balance', v_old_balance,
    'new_balance', v_new_balance,
    'debt_name', v_debt_name,
    'is_paid_off', v_new_balance <= 0
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
