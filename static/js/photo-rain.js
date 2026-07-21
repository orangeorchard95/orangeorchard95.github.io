/* 照片掉落效果 — 改编自 Codrops "Made With GSAP" (codrops_mwg)
   鼠标/手指滑动累积一定距离后，在指针处弹出一张本页照片，
   坠落到视口底部、弹跳，然后掉出屏幕。掉落层固定定位、不挡交互。 */
window.addEventListener("DOMContentLoaded", () => {
  if (typeof gsap === "undefined") return;

  // 收集本页照片：有 gallery 就只用 gallery 的图（避免混入头像等），否则退回文章图片
  const sources = [];
  const seen = new Set();
  let candidates = document.querySelectorAll(".gallery img");
  if (candidates.length === 0) {
    candidates = document.querySelectorAll("article img");
  }
  candidates.forEach((img) => {
    const src = img.currentSrc || img.getAttribute("src");
    if (src && !seen.has(src)) {
      seen.add(src);
      sources.push(src);
    }
  });
  if (sources.length === 0) return;

  // 独立掉落层：fixed + pointer-events:none，不影响页面布局和点击
  const root = document.createElement("div");
  root.className = "photo-rain";
  document.body.appendChild(root);

  let incr = 0,
    oldIncrX = 0,
    oldIncrY = 0,
    firstMove = true,
    indexImg = 0;

  const isCoarsePointer = window.matchMedia("(hover: none)").matches;
  const resetDist = window.innerWidth / (isCoarsePointer ? 6 : 8);

  function applyMove(clientX, clientY) {
    const valX = gsap.utils.clamp(0, window.innerWidth, clientX);
    const valY = gsap.utils.clamp(0, window.innerHeight, clientY);

    if (firstMove) {
      firstMove = false;
      oldIncrX = valX;
      oldIncrY = valY;
      return;
    }

    incr += Math.abs(valX - oldIncrX) + Math.abs(valY - oldIncrY);

    if (incr > resetDist) {
      incr = 0;
      createMedia(valX, valY, valX - oldIncrX, valY - oldIncrY);
    }

    oldIncrX = valX;
    oldIncrY = valY;
  }

  document.addEventListener("mousemove", (e) => applyMove(e.clientX, e.clientY));
  document.addEventListener(
    "touchstart",
    (e) => e.touches[0] && applyMove(e.touches[0].clientX, e.touches[0].clientY),
    { passive: true }
  );
  document.addEventListener(
    "touchmove",
    (e) => e.touches[0] && applyMove(e.touches[0].clientX, e.touches[0].clientY),
    { passive: true }
  );

  function createMedia(x, y, deltaX, deltaY) {
    const H = window.innerHeight;
    if (y > H - 200) return;

    const image = document.createElement("img");
    image.setAttribute("src", sources[indexImg]);
    root.appendChild(image);

    const tl = gsap.timeline({
      onComplete: () => {
        root.removeChild(image);
        tl && tl.kill();
      },
    });

    // 弹出：略放大 + 随机偏移旋转，弹性回落到原尺寸
    tl.fromTo(
      image,
      {
        xPercent: -50 + (Math.random() - 0.5) * 80,
        yPercent: -50 + (Math.random() - 0.5) * 10,
        scaleX: 1.3,
        scaleY: 1.3,
        rotation: (Math.random() - 0.5) * 20,
      },
      { scaleX: 1, scaleY: 1, ease: "elastic.out(2, 0.6)", duration: 0.4 }
    );

    // 沿鼠标方向水平漂移
    tl.fromTo(
      image,
      { x },
      { x: "+=" + deltaX * 2, rotation: 0, ease: "power1.in", duration: 0.4 },
      "<"
    );

    // 坠落到视口底部
    tl.fromTo(
      image,
      { y },
      {
        y: "+=" + (H - y),
        scale: 0.9,
        yPercent: -95,
        ease: "back.in(1.1)",
        duration: 0.4,
      },
      "<"
    );

    // 弹跳后掉出屏幕
    tl.to(image, {
      x: "+=" + deltaX * 1.6,
      rotation: (Math.random() - 0.5) * 40,
      ease: "power1.in",
      duration: 0.3,
    });
    tl.to(
      image,
      {
        yPercent: 150,
        ease: "back.in(" + (1.5 + (1 - y / H)) + ")",
        duration: 0.3,
      },
      "<"
    );

    indexImg = (indexImg + 1) % sources.length;
  }
});
