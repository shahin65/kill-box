(function () {
  var node = document.getElementById('kb-shop-kpis');
  if (!node || typeof window.Chart !== 'function') {
    return;
  }
  var data = {};
  try {
    data = JSON.parse(node.textContent || '{}');
  } catch (err) {
    return;
  }
  var line = document.getElementById('kb-shop-line');
  var donut = document.getElementById('kb-shop-donut');
  if (line) {
    new window.Chart(line, {
      type: 'line',
      data: {
        labels: data.daily_labels || [],
        datasets: [
          {
            label: 'درآمد روزانه',
            data: data.daily_values || [],
            borderColor: '#417690',
            backgroundColor: 'rgba(65, 118, 144, 0.18)',
            fill: true,
            tension: 0.25,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
      },
    });
  }
  if (donut) {
    new window.Chart(donut, {
      type: 'doughnut',
      data: {
        labels: data.donut_labels || [],
        datasets: [
          {
            data: data.donut_values || [],
            backgroundColor: ['#417690', '#79aec8', '#ba2121', '#266e34'],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '62%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 10, font: { size: 11 }, padding: 8 },
          },
        },
      },
    });
  }
})();
