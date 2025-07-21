// Chart initialization for GitHub metrics
function initializeCharts(chartData) {
    // Validate chart data
    if (!chartData || !chartData.labels || !chartData.datasets) {
        console.error('Chart data is invalid:', chartData);
        return;
    }

    // Chart configuration
    const chartConfig = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            }
        },
        scales: {
            y: {
                beginAtZero: true
            }
        }
    };

    // PR Throughput Chart
    const throughputCtx = document.getElementById('throughputChart');
    if (throughputCtx) {
        new Chart(throughputCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: chartData.datasets.pr_throughput.label,
                    data: chartData.datasets.pr_throughput.data,
                    backgroundColor: chartData.datasets.pr_throughput.backgroundColor,
                    borderColor: chartData.datasets.pr_throughput.borderColor,
                    borderWidth: chartData.datasets.pr_throughput.borderWidth
                }]
            },
            options: chartConfig
        });
    }

    // MR Time Chart
    const mrTimeCtx = document.getElementById('mrTimeChart');
    if (mrTimeCtx) {
        new Chart(mrTimeCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: chartData.datasets.mr_time.label,
                    data: chartData.datasets.mr_time.data,
                    backgroundColor: chartData.datasets.mr_time.backgroundColor,
                    borderColor: chartData.datasets.mr_time.borderColor,
                    borderWidth: chartData.datasets.mr_time.borderWidth,
                    fill: false,
                    tension: 0.1
                }]
            },
            options: chartConfig
        });
    }

    // First Commit to Merge Chart
    const commitToMergeCtx = document.getElementById('commitToMergeChart');
    if (commitToMergeCtx) {
        new Chart(commitToMergeCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: chartData.datasets.first_commit_to_merge.label,
                    data: chartData.datasets.first_commit_to_merge.data,
                    backgroundColor: chartData.datasets.first_commit_to_merge.backgroundColor,
                    borderColor: chartData.datasets.first_commit_to_merge.borderColor,
                    borderWidth: chartData.datasets.first_commit_to_merge.borderWidth
                }]
            },
            options: chartConfig
        });
    }

    // Weekly Activity Chart
    const weeklyCtx = document.getElementById('weeklyChart');
    if (weeklyCtx && chartData.weekly_data && chartData.weekly_data.labels) {
        const weeklyConfig = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of PRs'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Week'
                    }
                }
            }
        };

        new Chart(weeklyCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: chartData.weekly_data.labels,
                datasets: chartData.weekly_data.datasets
            },
            options: weeklyConfig
        });
    }

    // Contributors Chart
    const contributorsCtx = document.getElementById('contributorsChart');
    if (contributorsCtx && chartData.leaderboard_data && chartData.leaderboard_data.contributors) {
        const contributorsConfig = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.parsed.y} PRs`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Total PRs'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Contributors'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        };

        new Chart(contributorsCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: chartData.leaderboard_data.contributors.labels,
                datasets: [{
                    label: 'Total PRs',
                    data: chartData.leaderboard_data.contributors.data,
                    backgroundColor: chartData.leaderboard_data.contributors.backgroundColor,
                    borderColor: chartData.leaderboard_data.contributors.borderColor,
                    borderWidth: chartData.leaderboard_data.contributors.borderWidth
                }]
            },
            options: contributorsConfig
        });
    }

    // PR Size Chart
    const prSizeCtx = document.getElementById('prSizeChart');
    if (prSizeCtx && chartData.leaderboard_data && chartData.leaderboard_data.pr_sizes) {
        const prSizeConfig = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.parsed.y} lines avg`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Average PR Size (lines)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Contributors'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        };

        new Chart(prSizeCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: chartData.leaderboard_data.pr_sizes.labels,
                datasets: [{
                    label: 'Average PR Size',
                    data: chartData.leaderboard_data.pr_sizes.data,
                    backgroundColor: chartData.leaderboard_data.pr_sizes.backgroundColor,
                    borderColor: chartData.leaderboard_data.pr_sizes.borderColor,
                    borderWidth: chartData.leaderboard_data.pr_sizes.borderWidth,
                    fill: false,
                    tension: 0.1
                }]
            },
            options: prSizeConfig
        });
    }
}

// Initialize charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Get chart data from the page (will be set by template)
    if (typeof window.chartData !== 'undefined') {
        initializeCharts(window.chartData);
    }
}); 