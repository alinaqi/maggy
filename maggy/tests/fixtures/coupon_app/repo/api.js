// The coupon API: a tiny in-page server for the fixture. A seeded $100 cart and two codes;
// expiry is compared in UTC against a fixed clock, so every run renders the same state.
(function () {
  var NOW = Date.parse('2026-11-24T12:00:00Z');
  var CART = { subtotal: 100 };
  var COUPONS = {
    SAVE10: { percent: 10, expiresAt: '2027-01-01T00:00:00Z' },
    EXPIRED: { percent: 10, expiresAt: '2026-01-01T00:00:00Z' }
  };

  function apply(code) {
    var coupon = COUPONS[String(code).trim().toUpperCase()];
    if (!coupon) {
      return { ok: false, error: 'unknown', message: 'This coupon is not valid', total: CART.subtotal };
    }
    if (Date.parse(coupon.expiresAt) <= NOW) {
      return { ok: false, error: 'expired', message: 'This coupon has expired', total: CART.subtotal };
    }
    return { ok: true, total: CART.subtotal * (100 - coupon.percent) / 100 };
  }

  window.CouponApi = { cart: CART, apply: apply };
})();
