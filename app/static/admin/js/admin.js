var token = localStorage.getItem('admin_token');

if (!token) {
  window.location.href = '/admin';
}

function loadBanners() {
  fetch('/api/banners', {
    headers: {
      'Authorization': 'Bearer ' + token
    }
  })
    .then(function(r) {
      return r.json();
    })
    .then(function(d) {
      var tbody = document.getElementById('bannersTableBody');

      if (d.success && Array.isArray(d.data) && d.data.length) {
        tbody.innerHTML = d.data.map(function(b) {
          return '<tr>' +
            '<td><img src="' + b.image_url + '" style="width:80px;height:40px;object-fit:cover;"></td>' +
            '<td>' + (b.title || '—') + '</td>' +
            '<td>' + (b.position || '—') + '</td>' +
            '<td><span style="color:' + (b.is_active ? '#27ae60' : '#c0392b') + ';">' + (b.is_active ? 'Active' : 'Inactive') + '</span></td>' +
            '<td>' +
            '<a href="/admin/banners/' + b.id + '/edit" class="btn btn-ghost btn-sm">Edit</a>' +
            '<button class="btn btn-danger btn-sm" onclick="deleteBanner(\'' + b.id + '\')">Delete</button>' +
            '</td>' +
            '</tr>';
        }).join('');
      } else {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No banners found.</td></tr>';
      }
    })
    .catch(function() {
      document.getElementById('bannersTableBody').innerHTML = '<tr><td colspan="5" style="text-align:center;">Failed to load.</td></tr>';
    });
}

function deleteBanner(bannerId) {
  if (!confirm('Are you sure you want to delete this banner?')) return;

  fetch('/api/banners/' + bannerId, {
    method: 'DELETE',
    headers: {
      'Authorization': 'Bearer ' + token
    }
  })
    .then(function(r) {
      return r.json();
    })
    .then(function(d) {
      if (d.success) {
        loadBanners();
      } else {
        alert(d.error || 'Delete failed');
      }
    })
    .catch(function() {
      alert('Network error');
    });
}

document.addEventListener('DOMContentLoaded', loadBanners);