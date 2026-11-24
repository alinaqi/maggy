// Checkout controller: sends the entered code to the coupon API and renders the response.
(function () {
  var form = document.getElementById('coupon-form');
  var field = document.getElementById('coupon');
  var total = document.getElementById('order-total');

  function render(response) {
    total.textContent = 'Total: $' + response.total;
    if (!response.ok) {
      field.value = '';
    }
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    render(window.CouponApi.apply(field.value));
  });
})();
