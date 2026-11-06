(function (global) {
  'use strict';

  var TWO_PI = Math.PI * 2;
  var ENABLE_FOG = false;
  var TINT_GREEN = [
    [168, 186, 142],
    [148, 168, 128],
    [196, 210, 164],
    [132, 154, 118],
  ];
  var TINT_EMBER = [
    [214, 138, 86],
    [196, 108, 72],
    [206, 150, 96],
    [176, 98, 70],
  ];
  var TINT_ASH = [
    [198, 188, 168],
    [168, 158, 140],
    [132, 124, 110],
    [214, 176, 130],
    [110, 104, 92],
  ];

  function prefersReducedMotion() {
    return global.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function isMobileSurface() {
    return global.matchMedia('(pointer: coarse), (max-width: 768px)').matches;
  }

  function isIOSSurface() {
    return /iP(hone|ad|od)/.test(global.navigator.userAgent) ||
      (global.navigator.platform === 'MacIntel' && global.navigator.maxTouchPoints > 1);
  }

  function pickFrom(list) {
    return list[(Math.random() * list.length) | 0];
  }

  function rgba(tint, alpha) {
    return 'rgba(' + tint[0] + ',' + tint[1] + ',' + tint[2] + ',' + alpha + ')';
  }

  function capDpr() {
    var dpr = global.devicePixelRatio || 1;
    if (isIOSSurface()) {
      return Math.min(dpr, 1);
    }
    if (isMobileSurface()) {
      return Math.min(dpr, 1.15);
    }
    return Math.min(dpr, 1.4);
  }

  function loadImage(src) {
    return new Promise(function (resolve) {
      if (!src) {
        resolve(null);
        return;
      }
      var img = new Image();
      img.decoding = 'async';
      img.onload = function () {
        resolve(img);
      };
      img.onerror = function () {
        resolve(null);
      };
      img.src = src;
    });
  }

  function averageBand(data, width, y0, y1) {
    var r = 0;
    var g = 0;
    var b = 0;
    var n = 0;
    var y;
    var x;
    var i;
    for (y = y0; y < y1; y += 1) {
      for (x = 0; x < width; x += 1) {
        i = (y * width + x) * 4;
        r += data[i];
        g += data[i + 1];
        b += data[i + 2];
        n += 1;
      }
    }
    if (!n) {
      return [110, 112, 96];
    }
    return [(r / n) | 0, (g / n) | 0, (b / n) | 0];
  }

  function sampleSceneTints(img) {
    if (!img) {
      return [
        [118, 124, 98],
        [92, 96, 78],
        [72, 68, 56],
      ];
    }
    var canvas = document.createElement('canvas');
    canvas.width = 32;
    canvas.height = 18;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, 32, 18);
    var data = ctx.getImageData(0, 0, 32, 18).data;
    return [
      averageBand(data, 32, 0, 6),
      averageBand(data, 32, 6, 12),
      averageBand(data, 32, 12, 18),
    ];
  }

  function tintSprite(src, rgb, amount) {
    var canvas = document.createElement('canvas');
    canvas.width = src.naturalWidth || src.width;
    canvas.height = src.naturalHeight || src.height;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(src, 0, 0);
    ctx.globalCompositeOperation = 'source-atop';
    ctx.globalAlpha = amount;
    ctx.fillStyle = 'rgb(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ')';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
    return canvas;
  }

  function DustField(canvas, options) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d', { alpha: true });
    this.options = options || {};
    this.layer = this.options.layer || 'mixed';
    this.particles = [];
    this.clouds = [];
    this.w = 0;
    this.h = 0;
    this.mobile = false;
    this.wind = this.options.wind || 1;
    this.fogAlpha = this.options.fogAlpha == null ? 1 : this.options.fogAlpha;
    this.light = this.options.light == null ? 1 : this.options.light;
  }

  DustField.prototype.resize = function () {
    this.mobile = isMobileSurface();
    var dpr = capDpr();
    var width = this.canvas.clientWidth || this.canvas.offsetWidth;
    var height = this.canvas.clientHeight || this.canvas.offsetHeight;
    var sizeChanged = Math.abs(width - this.w) > 8 || Math.abs(height - this.h) > 8;
    this.w = width;
    this.h = height;
    this.canvas.width = Math.floor(width * dpr);
    this.canvas.height = Math.floor(height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (sizeChanged && (this.clouds.length || this.particles.length)) {
      this.seed();
    }
  };

  DustField.prototype.seed = function () {
    var front = this.layer === 'front';
    var back = this.layer === 'back';
    var dustCount = this.options.count;
    var cloudCount = this.options.clouds;
    var ios = isIOSSurface();

    if (!dustCount) {
      if (front) {
        dustCount = ios ? 6 : this.mobile ? 8 : 12;
      } else if (back) {
        dustCount = ios ? 4 : this.mobile ? 5 : 8;
      } else {
        dustCount = ios ? 5 : this.mobile ? 6 : 10;
      }
    }
    if (!ENABLE_FOG) {
      cloudCount = 0;
    } else if (!cloudCount) {
      if (front) {
        cloudCount = this.mobile ? 5 : 7;
      } else if (back) {
        cloudCount = this.mobile ? 6 : 8;
      } else {
        cloudCount = this.mobile ? 6 : 8;
      }
      cloudCount = Math.max(4, Math.min(10, cloudCount));
    }

    this.particles = [];
    for (var i = 0; i < dustCount; i += 1) {
      this.particles.push(this.spawnDust(true));
    }
    this.clouds = [];
    for (var c = 0; c < cloudCount; c += 1) {
      this.clouds.push(this.spawnCloud(true));
    }
  };

  DustField.prototype.speedScale = function () {
    if (this.layer === 'front') {
      return 1;
    }
    if (this.layer === 'back') {
      return 0.42;
    }
    return 0.7;
  };

  DustField.prototype.pickTint = function (yNorm) {
    var emberChance;
    if (this.layer === 'front') {
      emberChance = yNorm > 0.52 ? 0.72 : 0.42;
    } else if (this.layer === 'back') {
      emberChance = yNorm > 0.62 ? 0.32 : 0.16;
    } else {
      emberChance = yNorm > 0.55 ? 0.5 : 0.3;
    }
    return Math.random() < emberChance ? pickFrom(TINT_EMBER) : pickFrom(TINT_GREEN);
  };

  DustField.prototype.spawnDust = function (anywhere) {
    var yNorm = anywhere ? Math.random() : 1.02 + Math.random() * 0.08;
    var front = this.layer === 'front';
    var flake = Math.random() < 0.35;
    return {
      x: Math.random() * this.w,
      y: anywhere ? yNorm * this.h : this.h + 12,
      r: flake ? 1.4 + Math.random() * 2.8 : 0.45 + Math.random() * 1.4,
      vx: this.wind * this.speedScale() * (0.045 + Math.random() * 0.08),
      vy: -0.055 + Math.random() * 0.1,
      a: 0.28 + Math.random() * 0.42,
      phase: Math.random() * TWO_PI,
      flicker: 0.0018 + Math.random() * 0.0024,
      tint: Math.random() < 0.7 ? pickFrom(TINT_ASH) : this.pickTint(yNorm),
      front: front,
    };
  };

  DustField.prototype.spawnCloud = function (anywhere) {
    var front = this.layer === 'front';
    var back = this.layer === 'back';
    var band = Math.random();
    var yNorm;
    if (front) {
      yNorm = band < 0.8 ? 0.5 + Math.random() * 0.42 : 0.32 + Math.random() * 0.16;
    } else if (back) {
      yNorm = band < 0.68 ? 0.34 + Math.random() * 0.48 : 0.18 + Math.random() * 0.16;
    } else {
      yNorm = band < 0.75 ? 0.46 + Math.random() * 0.44 : 0.28 + Math.random() * 0.16;
    }

    var low = yNorm > 0.55;
    var wisp = front && Math.random() < 0.38;
    var sizeBoost = (back ? 1.02 : 0.82) + yNorm * 0.42;
    if (wisp) {
      sizeBoost *= 0.48;
    }
    var diameter = (this.mobile
      ? 220 + Math.random() * 200
      : 280 + Math.random() * 260) * sizeBoost;
    var radius = diameter * 0.5;
    var x;
    if (anywhere) {
      x = Math.random() * (this.w + diameter) - radius;
    } else if (this.wind > 0) {
      x = -radius - 40;
    } else {
      x = this.w + radius + 40;
    }

    var baseA = wisp ? 0.26 + Math.random() * 0.16 : 0.2 + Math.random() * 0.16;
    if (low) {
      baseA += 0.06;
    }
    if (front && !wisp) {
      baseA += 0.04;
    }

    var speed = this.speedScale() * (wisp ? 1.7 : 1) * (0.055 + Math.random() * 0.05);

    return {
      x: x,
      baseY: this.h * yNorm,
      y: this.h * yNorm,
      r: radius,
      stretch: (low ? 1.55 : 1.2) + Math.random() * 0.4,
      flatten: (low ? 0.58 : 0.46) + Math.random() * 0.16,
      vx: this.wind * speed,
      vy: (-0.008 + Math.random() * 0.016) * this.speedScale(),
      baseA: Math.min(0.48, baseA),
      phase: Math.random() * TWO_PI,
      breath: 0.0007 + Math.random() * 0.00055,
      bob: 22 + Math.random() * 28,
      tint: this.pickTint(yNorm),
      wisp: wisp,
    };
  };

  DustField.prototype.step = function (now, dt) {
    if (ENABLE_FOG) {
      this.drawClouds(now, dt);
    }
    this.drawDust(now, dt);
  };

  DustField.prototype.draw = function (now, dt) {
    var ctx = this.ctx;
    ctx.globalCompositeOperation = 'source-over';
    ctx.clearRect(0, 0, this.w, this.h);
    ctx.globalCompositeOperation = this.layer === 'back' ? 'screen' : 'source-over';
    ctx.globalAlpha = this.layer === 'back' ? Math.max(0, this.light) : 1;
    this.step(now, dt);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  };

  DustField.prototype.drawClouds = function (now, dt) {
    var ctx = this.ctx;
    for (var i = 0; i < this.clouds.length; i += 1) {
      var cloud = this.clouds[i];
      cloud.x += cloud.vx * dt;
      cloud.baseY += cloud.vy * dt;
      cloud.y = cloud.baseY + Math.sin(now * 0.00055 + cloud.phase) * cloud.bob;

      var margin = cloud.r * cloud.stretch + 48;
      if (cloud.x < -margin || cloud.x > this.w + margin) {
        this.clouds[i] = this.spawnCloud(false);
        cloud = this.clouds[i];
      }

      var pulse = 0.5 + 0.5 * Math.sin(now * cloud.breath + cloud.phase);
      var alpha = cloud.baseA * (0.42 + 0.58 * pulse) * this.fogAlpha;
      var tint = cloud.tint;
      var gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, cloud.r);
      gradient.addColorStop(0, rgba(tint, alpha));
      gradient.addColorStop(0.38, rgba(tint, alpha * 0.5));
      gradient.addColorStop(1, rgba(tint, 0));

      ctx.save();
      ctx.translate(cloud.x, cloud.y);
      ctx.scale(cloud.stretch, cloud.flatten);
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(0, 0, cloud.r, 0, TWO_PI);
      ctx.fill();
      ctx.restore();
    }
  };

  DustField.prototype.drawDust = function (now, dt) {
    var ctx = this.ctx;
    for (var i = 0; i < this.particles.length; i += 1) {
      var p = this.particles[i];
      p.x += p.vx * dt;
      p.y += p.vy * dt + Math.sin(now * 0.0011 + p.phase) * 0.04;
      if (p.x < -48 || p.x > this.w + 48 || p.y < -48 || p.y > this.h + 48) {
        this.particles[i] = this.spawnDust(false);
        continue;
      }
      var flicker = 0.62 + 0.38 * Math.sin(now * p.flicker + p.phase);
      ctx.beginPath();
      ctx.fillStyle = rgba(p.tint, p.a * flicker * this.fogAlpha);
      ctx.arc(p.x, p.y, p.r, 0, TWO_PI);
      ctx.fill();
    }
  };

  function SpriteField(canvas, options) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d', { alpha: true });
    this.options = options || {};
    this.kind = this.options.kind || 'ash';
    this.layer = this.options.layer || 'front';
    this.sprite = this.options.sprite;
    this.sprites = this.options.sprites || (this.sprite ? [this.sprite] : []);
    this.particles = [];
    this.w = 0;
    this.h = 0;
    this.mobile = false;
    this.wind = this.options.wind || 1;
    this.fogAlpha = this.options.fogAlpha == null ? 1 : this.options.fogAlpha;
    this.light = this.options.light == null ? 1 : this.options.light;
  }

  SpriteField.prototype.resize = function () {
    this.mobile = isMobileSurface();
    var dpr = capDpr();
    var width = this.canvas.clientWidth || this.canvas.offsetWidth;
    var height = this.canvas.clientHeight || this.canvas.offsetHeight;
    var sizeChanged = Math.abs(width - this.w) > 8 || Math.abs(height - this.h) > 8;
    this.w = width;
    this.h = height;
    this.canvas.width = Math.floor(width * dpr);
    this.canvas.height = Math.floor(height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (sizeChanged) {
      this.seed();
    }
  };

  SpriteField.prototype.speedScale = function () {
    if (this.layer === 'front') {
      return 1;
    }
    if (this.layer === 'back') {
      return 0.42;
    }
    return 0.7;
  };

  SpriteField.prototype.count = function () {
    var ios = isIOSSurface();
    var front = this.layer === 'front';
    if (this.kind === 'ash') {
      if (front) {
        return ios ? 6 : this.mobile ? 8 : 12;
      }
      return ios ? 4 : this.mobile ? 5 : 8;
    }
    if (front) {
      return ios ? 5 : this.mobile ? 7 : 9;
    }
    return ios ? 6 : this.mobile ? 8 : 11;
  };

  SpriteField.prototype.seed = function () {
    this.particles = [];
    if (!this.sprite && !this.sprites.length) {
      return;
    }
    var n = this.options.count || this.count();
    for (var i = 0; i < n; i += 1) {
      this.particles.push(this.spawn(true));
    }
  };

  SpriteField.prototype.pickSprite = function (band) {
    if (this.sprites && this.sprites.length) {
      return this.sprites[Math.min(band, this.sprites.length - 1)] || this.sprites[0];
    }
    return this.sprite;
  };

  SpriteField.prototype.windEnterX = function (size) {
    if (this.wind >= 0) {
      return -size * 0.28;
    }
    return this.w + size * 0.28;
  };

  SpriteField.prototype.isGone = function (p) {
    var m = p.size + 56;
    return p.age > p.maxAge || p.x < -m || p.x > this.w + m || p.y < -m || p.y > this.h + m;
  };

  SpriteField.prototype.spawn = function (anywhere) {
    if (this.kind === 'ash') {
      return this.spawnAsh(anywhere);
    }
    return this.spawnSmoke(anywhere);
  };

  SpriteField.prototype.spawnAsh = function (anywhere) {
    var front = this.layer === 'front';
    var flake = Math.random() < 0.35;
    var radius = flake ? 2.4 + Math.random() * 4.2 : 0.9 + Math.random() * 2.2;
    var size = radius * 2;
    var yNorm = anywhere ? Math.random() : 1.02 + Math.random() * 0.08;
    return {
      x: Math.random() * this.w,
      y: anywhere ? yNorm * this.h : this.h + 12,
      size: size,
      rot: Math.random() * TWO_PI,
      vr: (-0.0018 + Math.random() * 0.0036) * (flake ? 0.7 : 0.35),
      vx: this.wind * this.speedScale() * (0.045 + Math.random() * 0.08),
      vy: -0.055 + Math.random() * 0.1,
      a: 0.32 + Math.random() * 0.4,
      glow: (front ? 0.18 : 0.1) * (flake ? 1 : 0.55),
      phase: Math.random() * TWO_PI,
      flicker: 0.0018 + Math.random() * 0.0024,
      age: anywhere ? Math.random() * 2200 : 0,
      maxAge: 7000 + Math.random() * 8000,
    };
  };

  SpriteField.prototype.spawnSmoke = function (anywhere) {
    var front = this.layer === 'front';
    var yNorm = anywhere ? Math.random() : Math.random();
    var band = yNorm < 0.33 ? 0 : yNorm < 0.66 ? 1 : 2;
    var size0 = (this.mobile ? 70 : 90) + Math.random() * (this.mobile ? 70 : 90);
    if (front) {
      size0 *= 0.78;
    }
    return {
      x: anywhere ? Math.random() * this.w : this.windEnterX(size0),
      y: this.h * yNorm,
      size0: size0,
      size: size0,
      grow: 0.7 + Math.random() * 0.9,
      rot: (Math.random() - 0.5) * 0.18,
      vr: 0,
      vx: this.wind * this.speedScale() * (front ? 0.028 : 0.018) * (0.92 + Math.random() * 0.16),
      vy: -0.018 + Math.random() * 0.03,
      a: front ? 0.22 + Math.random() * 0.16 : 0.28 + Math.random() * 0.18,
      stretch: 1.18 + Math.random() * 0.28,
      flatten: 0.78 + Math.random() * 0.14,
      phase: Math.random() * TWO_PI,
      band: band,
      sprite: this.pickSprite(band),
      age: anywhere ? Math.random() * 2500 : 0,
      maxAge: 9000 + Math.random() * 7000,
    };
  };

  SpriteField.prototype.draw = function (now, dt) {
    var ctx = this.ctx;
    ctx.globalCompositeOperation = 'source-over';
    ctx.clearRect(0, 0, this.w, this.h);
    if (!this.sprite && !this.sprites.length) {
      return;
    }
    if (!this.particles.length) {
      this.seed();
    }
    var light = Math.max(0, this.light);
    for (var i = 0; i < this.particles.length; i += 1) {
      var p = this.particles[i];
      p.age += dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      if (this.kind === 'ash') {
        p.y += Math.sin(now * 0.0011 + p.phase) * 0.04;
      }
      if (p.vr) {
        p.rot += p.vr * dt;
      }
      if (this.isGone(p)) {
        this.particles[i] = this.spawn(false);
        p = this.particles[i];
      }
      var t = Math.max(0, Math.min(1, p.age / p.maxAge));
      if (p.size0) {
        p.size = p.size0 * (1 + p.grow * t);
      }
      var fade = 1;
      if (t < 0.12) {
        fade = t / 0.12;
      } else if (t > 0.72) {
        fade = (1 - t) / 0.28;
      }
      var alpha = p.a * fade * this.fogAlpha * light;
      if (p.flicker) {
        alpha *= 0.7 + 0.3 * (0.5 + 0.5 * Math.sin(now * p.flicker + p.phase));
      }
      var sprite = p.sprite || this.sprite;
      ctx.save();
      ctx.translate(p.x, p.y);
      if (this.kind === 'ash' && p.glow) {
        var glowA = p.glow * fade * light * (0.55 + 0.45 * (0.5 + 0.5 * Math.sin(now * (p.flicker || 0.002) + p.phase)));
        ctx.globalCompositeOperation = 'screen';
        var rad = p.size * 0.85;
        var glow = ctx.createRadialGradient(0, 0, 0, 0, 0, rad);
        glow.addColorStop(0, 'rgba(255, 64, 18, ' + (glowA * 0.95) + ')');
        glow.addColorStop(0.28, 'rgba(220, 28, 8, ' + (glowA * 0.42) + ')');
        glow.addColorStop(1, 'rgba(80, 0, 0, 0)');
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(0, 0, rad, 0, TWO_PI);
        ctx.fill();
        ctx.globalCompositeOperation = 'source-over';
      }
      ctx.rotate(p.rot || 0);
      ctx.scale(p.stretch || 1, p.flatten || 1);
      ctx.globalAlpha = alpha;
      if (sprite) {
        ctx.drawImage(sprite, -p.size * 0.5, -p.size * 0.5, p.size, p.size);
      }
      ctx.restore();
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  };

  function FogDirector() {
    this.fields = [];
    this.raf = 0;
    this.running = false;
    this.last = 0;
    this._tick = this.tick.bind(this);
    this._onResize = this.resize.bind(this);
    this._onVis = this.onVisibility.bind(this);
  }

  FogDirector.prototype.add = function (field) {
    if (this.fogAlpha != null) {
      field.fogAlpha = this.fogAlpha;
    }
    if (this.light != null) {
      field.light = this.light;
    }
    this.fields.push(field);
    return this;
  };

  FogDirector.prototype.start = function () {
    this.resize();
    for (var i = 0; i < this.fields.length; i += 1) {
      this.fields[i].seed();
    }
    if (prefersReducedMotion()) {
      this.draw(performance.now(), 0);
      return this;
    }
    global.addEventListener('resize', this._onResize, { passive: true });
    document.addEventListener('visibilitychange', this._onVis);
    this.running = true;
    this.last = performance.now();
    this.raf = global.requestAnimationFrame(this._tick);
    return this;
  };

  FogDirector.prototype.destroy = function () {
    this.running = false;
    global.cancelAnimationFrame(this.raf);
    global.removeEventListener('resize', this._onResize);
    document.removeEventListener('visibilitychange', this._onVis);
  };

  FogDirector.prototype.resize = function () {
    for (var i = 0; i < this.fields.length; i += 1) {
      this.fields[i].resize();
    }
  };

  FogDirector.prototype.onVisibility = function () {
    if (document.hidden) {
      this.running = false;
      global.cancelAnimationFrame(this.raf);
      return;
    }
    this.running = true;
    this.last = performance.now();
    this.raf = global.requestAnimationFrame(this._tick);
  };

  FogDirector.prototype.tick = function (now) {
    if (!this.running) {
      return;
    }
    var dt = Math.min(33, now - this.last);
    this.last = now;
    this.draw(now, dt);
    this.raf = global.requestAnimationFrame(this._tick);
  };

  FogDirector.prototype.draw = function (now, dt) {
    for (var i = 0; i < this.fields.length; i += 1) {
      this.fields[i].draw(now, dt);
    }
  };

  FogDirector.prototype.setAtmosphere = function (fogAlpha, light) {
    this.fogAlpha = fogAlpha;
    this.light = light;
    for (var i = 0; i < this.fields.length; i += 1) {
      this.fields[i].fogAlpha = Math.max(0, fogAlpha);
      this.fields[i].light = Math.max(0, light);
    }
  };

  function mountFields(director, canvases, wind) {
    var smokeSprites = canvases.smokeSprites || (canvases.smokeSprite ? [canvases.smokeSprite] : []);
    if (canvases.fogBack) {
      director.add(new DustField(canvases.fogBack, { layer: 'back', wind: wind }));
    }
    if (canvases.fogFront) {
      director.add(new DustField(canvases.fogFront, { layer: 'front', wind: wind }));
    }
    if (canvases.smokeBack && smokeSprites.length) {
      director.add(new SpriteField(canvases.smokeBack, {
        kind: 'smoke',
        layer: 'back',
        wind: wind,
        sprite: smokeSprites[1] || smokeSprites[0],
        sprites: smokeSprites,
      }));
    }
    if (canvases.smokeFront && smokeSprites.length) {
      director.add(new SpriteField(canvases.smokeFront, {
        kind: 'smoke',
        layer: 'front',
        wind: wind,
        sprite: smokeSprites[1] || smokeSprites[0],
        sprites: smokeSprites,
      }));
    }
    if (canvases.ashBack && canvases.ashSprite) {
      director.add(new SpriteField(canvases.ashBack, {
        kind: 'ash',
        layer: 'back',
        wind: wind,
        sprite: canvases.ashSprite,
      }));
    }
    if (canvases.ashFront && canvases.ashSprite) {
      director.add(new SpriteField(canvases.ashFront, {
        kind: 'ash',
        layer: 'front',
        wind: wind,
        sprite: canvases.ashSprite,
      }));
    }
    director.start();
    global.KillBoxParticles.last = director;
    return director;
  }

  global.KillBoxParticles = {
    ENABLE_FOG: ENABLE_FOG,
    mount: function (canvas, options) {
      return new FogDirector().add(new DustField(canvas, options || {})).start();
    },
    mountParallax: function (backCanvas, frontCanvas, options) {
      options = options || {};
      var wind = options.wind || (Math.random() < 0.35 ? -1 : 1);
      var back = new DustField(backCanvas, { layer: 'back', wind: wind });
      var front = new DustField(frontCanvas, { layer: 'front', wind: wind });
      return new FogDirector().add(back).add(front).start();
    },
    mountScene: function (cfg) {
      cfg = cfg || {};
      if (global.KillBoxParticles.last && global.KillBoxParticles.last.running) {
        var live = cfg.smokeBack || cfg.fogBack;
        if (live && live.isConnected) {
          return global.KillBoxParticles.last;
        }
      }
      var director = new FogDirector();
      var wind = cfg.wind || (Math.random() < 0.35 ? -1 : 1);
      var smokeUrl = (cfg.smokeBack && cfg.smokeBack.getAttribute('data-sprite')) ||
        (cfg.smokeFront && cfg.smokeFront.getAttribute('data-sprite')) || '';
      var ashUrl = (cfg.ashFront && cfg.ashFront.getAttribute('data-sprite')) ||
        (cfg.ashBack && cfg.ashBack.getAttribute('data-sprite')) ||
        (cfg.ash && cfg.ash.getAttribute('data-sprite')) || '';
      var sceneUrl = cfg.sceneUrl || '';

      Promise.all([loadImage(smokeUrl), loadImage(ashUrl), loadImage(sceneUrl)]).then(function (sprites) {
        var smokeSrc = sprites[0];
        var tints = sampleSceneTints(sprites[2]);
        var smokeSprites = smokeSrc
          ? [
            tintSprite(smokeSrc, tints[0], 0.32),
            tintSprite(smokeSrc, tints[1], 0.36),
            tintSprite(smokeSrc, tints[2], 0.34),
          ]
          : [];
        mountFields(director, {
          fogBack: cfg.fogBack,
          fogFront: cfg.fogFront,
          smokeBack: cfg.smokeBack,
          smokeFront: cfg.smokeFront,
          ashBack: cfg.ashBack,
          ashFront: cfg.ashFront || cfg.ash,
          smokeSprites: smokeSprites,
          ashSprite: sprites[1],
        }, wind);
      });
      return director;
    },
  };
})(window);
