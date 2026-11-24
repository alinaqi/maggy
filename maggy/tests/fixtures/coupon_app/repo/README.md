# Coupon checkout fixture

A static checkout page with a seeded $100 cart (`api.js` is the tiny coupon API) and the
codes `SAVE10` (10% off) and `EXPIRED`. Open `checkout.html` in a browser.

Known bug: applying `EXPIRED` clears the field and shows no field error.
