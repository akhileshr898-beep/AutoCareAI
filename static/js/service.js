// Service related JavaScript
document.addEventListener('DOMContentLoaded', () => {
    // Form validation for service
    const serviceForm = document.getElementById('serviceForm');
    if (serviceForm) {
        serviceForm.addEventListener('submit', (e) => {
            const cost = document.querySelector('input[name="total_cost"]');
            if (cost && parseFloat(cost.value) < 0) {
                e.preventDefault();
                alert('Cost cannot be negative');
            }
        });
    }
});
