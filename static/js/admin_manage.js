// Minimal JS for Modals
function toggleModal(modalId) {
  const modal = document.getElementById(modalId)
  if (modal.style.display === "block") {
    modal.style.display = "none"
  } else {
    modal.style.display = "block"
  }
}

function openEditModal(btn) {
  const modal = document.getElementById('classModal');
  modal.style.display = "block";
  
  const editUrl = btn.dataset.url;
  const session = JSON.parse(btn.dataset.session);
  
  document.getElementById('class_name').value = session.class_name;
  document.getElementById('pool_id').value = session.pool_id;
  document.getElementById('class_type_id').value = session.class_type_id;
  document.getElementById('user_id').value = session.user_id;
  document.getElementById('start_date').value = session.start_date;
  document.getElementById('end_date').value = session.end_date;
  document.getElementById('start_time').value = session.start_time;
  document.getElementById('end_time').value = session.end_time;
  document.getElementById('seats').value = session.seats;
  document.getElementById('total_sessions').value = session.total_sessions;

  document.querySelector('#classModal form').action = editUrl; // adjust id if needed
  document.querySelector('#classModal h2').textContent = "Edit Class Session";
}

function openEditPoolModal(btn) {
    // Open the modal
    const modal = document.getElementById('poolModal');
    modal.style.display = "block";

    // Get the URL for form submission
    const editUrl = btn.dataset.url;

    // Parse the pool data from the data attribute
    const pool = JSON.parse(btn.dataset.pool);

    // Populate modal fields
    document.getElementById('name').value = pool.name;
    document.getElementById('address').value = pool.address;
    document.getElementById('capacity').value = pool.capacity;
    document.getElementById('coordinates').value = pool.coordinates;

    // Update the form action
    document.querySelector('#poolModal form').action = editUrl;

    // Change the modal title
    document.querySelector('#poolModal h2').textContent = "Edit Pool";
}

function openEditClassTypeModal(btn) {
    const modal = document.getElementById('classTypeModal');
    modal.style.display = "block";

    const editUrl = btn.dataset.url;
    const type = JSON.parse(btn.dataset.classType);

    // Populate modal fields
    document.getElementById('type_name').value = type.name;
    document.getElementById('cost').value = type.cost;
    document.getElementById('description').value = type.description;


    // Update form action
    document.querySelector('#classTypeModal form').action = editUrl;
    document.querySelector('#classTypeModal h2').textContent = "Edit Class Type";
}


// Close modal when clicking outside
window.onclick = (event) => {
  if (event.target.classList.contains("modal")) {
    event.target.style.display = "none"
  }
}

// window.confirmCancel = function(classId) {
//   console.log("Attempting to cancel class with ID:", classId)
//   if (confirm("Are you sure you want to cancel this class session?")) {
//     window.location.href = `cancel_class/${classId}/`
//   }
// }