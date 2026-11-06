document.addEventListener('DOMContentLoaded', function () {
  var back = document.getElementById('fog-back');
  var front = document.getElementById('fog-front');
  if (!window.KillBoxParticles) {
    return;
  }
  if (back && front && window.KillBoxParticles.mountParallax) {
    window.KillBoxParticles.mountParallax(back, front);
    return;
  }
  if (back) {
    window.KillBoxParticles.mount(back);
  }
});
