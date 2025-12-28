// Mobile menu toggle
document.addEventListener("DOMContentLoaded", () => {
  const mobileMenuBtn = document.getElementById("mobileMenuBtn")
  const navMenu = document.getElementById("navMenu")

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener("click", () => {
      navMenu.classList.toggle("active")
    })
  }

  // Form handling for login
  const loginForm = document.getElementById("loginForm")
  if (loginForm) {
    loginForm.addEventListener("submit", (e) => {
      // Django will handle form submission
      console.log("Login form submitted")
    })
  }

  // Form handling for signup
  const signupForm = document.getElementById("signupForm")
  if (signupForm) {
    signupForm.addEventListener("submit", (e) => {
      const password = document.getElementById("password").value
      const confirmPassword = document.getElementById("confirmPassword").value

      if (password !== confirmPassword) {
        e.preventDefault()
        alert("Passwords do not match!")
        return false
      }
      // Django will handle form submission
      console.log("Signup form submitted")
    })
  }
})
