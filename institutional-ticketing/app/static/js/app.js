document.addEventListener('DOMContentLoaded', function () {
  const departmentSelect = document.getElementById('departmentSelect');
  const categorySelect = document.getElementById('categorySelect');

  function renderCategories() {
    if (!departmentSelect || !categorySelect) return;
    const selected = departmentSelect.options[departmentSelect.selectedIndex];
    const departmentName = selected ? selected.dataset.name : '';
    const categories = window.categoryMap[departmentName] || [];
    categorySelect.innerHTML = '<option value="">Select category</option>';
    categories.forEach((category) => {
      const opt = document.createElement('option');
      opt.value = category;
      opt.textContent = category;
      categorySelect.appendChild(opt);
    });
  }

  if (departmentSelect) {
    departmentSelect.addEventListener('change', renderCategories);
    renderCategories();
  }
});
