/*
  Custom JavaScript for Smart Employee Tracker
  - Initializes Chart.js charts when the analytics page has data
  - Contains small helpers used across the frontend
  - All functions are commented for clarity
*/

// Helper: create a line chart given canvas id, labels and data
function createLineChart(canvasId, labels, data, labelText) {
  // If canvas element does not exist, exit silently
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: labelText,
        data: data,
        borderColor: 'rgba(54, 162, 235, 1)',
        backgroundColor: 'rgba(54, 162, 235, 0.2)',
        tension: 0.2
      }]
    },
    options: { responsive: true }
  });
}

// Helper: create a bar chart
function createBarChart(canvasId, labels, data, labelText) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: labelText,
        data: data,
        backgroundColor: 'rgba(75, 192, 192, 0.6)'
      }]
    },
    options: { responsive: true }
  });
}

// When DOM loads, attempt to render analytics charts if data variables are present
document.addEventListener('DOMContentLoaded', function() {
  try {
    // Attendance chart uses the global variables set by analytics template
    if (typeof attendanceLabels !== 'undefined') {
      createLineChart('attendanceChart', attendanceLabels, attendanceData, 'Attendance');
    }
    if (typeof tasksLabels !== 'undefined') {
      createLineChart('tasksChart', tasksLabels, tasksData, 'Tasks Completed');
    }
    if (typeof deptLabels !== 'undefined') {
      createBarChart('deptChart', deptLabels, deptData, 'Employees per Department');
    }
    if (typeof topLabels !== 'undefined') {
      createBarChart('topChart', topLabels, topData, 'Top Performers');
    }
  } catch (e) {
    // Chart rendering errors should not break the app; log for debugging
    console.error('Chart rendering error:', e);
  }
});
