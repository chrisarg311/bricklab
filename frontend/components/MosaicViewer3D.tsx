"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { PALETTE } from "@/lib/mosaic";

interface Props {
  indices: number[];
  gridW: number;
  gridH: number;
  depths?: number[] | null;
  hoveredHex?: string | null;
}

export default function MosaicViewer3D({ indices, gridW, gridH, depths, hoveredHex }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const bodyMeshRef = useRef<THREE.InstancedMesh | null>(null);
  const studMeshRef = useRef<THREE.InstancedMesh | null>(null);
  const instanceHexesRef = useRef<string[]>([]);
  const [autoRotate, setAutoRotate] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    const W = el.clientWidth || 800;
    const H = el.clientHeight || 520;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);
    scene.fog = new THREE.FogExp2(0x0f172a, 0.004);

    const BRICK_W = 0.9, BRICK_H = 0.32, BRICK_D = 0.9;
    const STUD_R = 0.215, STUD_H = 0.14;

    // Compute total instances (one per brick in every column)
    const maxColumnHeight = depths
      ? Math.max(...depths)
      : 1;
    const total = depths
      ? depths.reduce((s, h) => s + h, 0)
      : gridW * gridH;

    // Camera
    const diag = Math.sqrt(gridW * gridW + gridH * gridH);
    const modelH = maxColumnHeight * BRICK_H;
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 2000);
    camera.position.set(0, Math.max(diag * 0.45, modelH * 2), diag * 0.9);
    camera.lookAt(0, modelH * 0.4, 0);

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const sun = new THREE.DirectionalLight(0xfff8e7, 1.1);
    sun.position.set(gridW * 0.4, gridH + modelH, gridW * 0.3);
    sun.castShadow = true;
    sun.shadow.mapSize.setScalar(2048);
    sun.shadow.camera.near = 0.1;
    sun.shadow.camera.far = diag * 4;
    sun.shadow.camera.left = -gridW;
    sun.shadow.camera.right = gridW;
    sun.shadow.camera.top = gridH + modelH;
    sun.shadow.camera.bottom = -gridH;
    scene.add(sun);
    const fill = new THREE.DirectionalLight(0xc8d8ff, 0.28);
    fill.position.set(-gridW, modelH, -gridH * 0.3);
    scene.add(fill);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.55;
    controls.minDistance = 3;
    controls.maxDistance = diag * 3;
    controls.maxPolarAngle = Math.PI / 1.7;
    controls.target.set(0, modelH * 0.3, 0);
    controlsRef.current = controls;

    // Geometries + materials
    const bodyGeo = new THREE.BoxGeometry(BRICK_W, BRICK_H, BRICK_D);
    const studGeo = new THREE.CylinderGeometry(STUD_R, STUD_R, STUD_H, 16);
    const bodyMat = new THREE.MeshStandardMaterial({ roughness: 0.55, metalness: 0.0 });
    const studMat = new THREE.MeshStandardMaterial({ roughness: 0.45, metalness: 0.0 });

    const bodyMesh = new THREE.InstancedMesh(bodyGeo, bodyMat, total);
    const studMesh = new THREE.InstancedMesh(studGeo, studMat, total);
    bodyMesh.castShadow = true;
    bodyMesh.receiveShadow = true;
    studMesh.castShadow = true;

    const dummy = new THREE.Object3D();
    const color = new THREE.Color();
    const offX = (gridW - 1) / 2;
    const offZ = (gridH - 1) / 2;

    const instanceHexes: string[] = new Array(total);
    let idx = 0;
    for (let y = 0; y < gridH; y++) {
      for (let x = 0; x < gridW; x++) {
        const cell = y * gridW + x;
        const hex = PALETTE[indices[cell]].hex;
        const colH = depths ? depths[cell] : 1;
        const wx = x - offX;
        const wz = y - offZ;

        for (let lvl = 0; lvl < colH; lvl++) {
          const wy = (lvl + 0.5) * BRICK_H;
          dummy.position.set(wx, wy, wz);
          dummy.rotation.set(0, 0, 0);
          dummy.scale.set(1, 1, 1);
          dummy.updateMatrix();
          bodyMesh.setMatrixAt(idx, dummy.matrix);
          color.set(hex);
          bodyMesh.setColorAt(idx, color);

          dummy.position.set(wx, (lvl + 1) * BRICK_H + STUD_H / 2, wz);
          dummy.updateMatrix();
          studMesh.setMatrixAt(idx, dummy.matrix);
          color.set(hex);
          color.offsetHSL(0, 0, 0.07);
          studMesh.setColorAt(idx, color);

          instanceHexes[idx] = hex;
          idx++;
        }
      }
    }

    instanceHexesRef.current = instanceHexes;

    bodyMesh.instanceMatrix.needsUpdate = true;
    studMesh.instanceMatrix.needsUpdate = true;
    if (bodyMesh.instanceColor) bodyMesh.instanceColor.needsUpdate = true;
    if (studMesh.instanceColor) studMesh.instanceColor.needsUpdate = true;

    bodyMeshRef.current = bodyMesh;
    studMeshRef.current = studMesh;

    scene.add(bodyMesh);
    scene.add(studMesh);

    // Baseplate
    const plateGeo = new THREE.BoxGeometry(gridW + 1, 0.12, gridH + 1);
    const plateMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.8 });
    const plate = new THREE.Mesh(plateGeo, plateMat);
    plate.position.y = -0.06;
    plate.receiveShadow = true;
    scene.add(plate);

    setLoaded(true);

    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const ro = new ResizeObserver(() => {
      const w = el.clientWidth, h = el.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    ro.observe(el);

    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
      controls.dispose();
      bodyGeo.dispose();
      studGeo.dispose();
      plateGeo.dispose();
      bodyMat.dispose();
      studMat.dispose();
      plateMat.dispose();
      renderer.dispose();
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement);
      controlsRef.current = null;
      setLoaded(false);
    };
  }, [indices, gridW, gridH, depths]);

  useEffect(() => {
    const body = bodyMeshRef.current;
    const stud = studMeshRef.current;
    const hexes = instanceHexesRef.current;
    if (!body || !stud || !hexes.length) return;

    const c = new THREE.Color();
    for (let i = 0; i < hexes.length; i++) {
      const hex = hexes[i];
      const dim = hoveredHex !== null && hoveredHex !== undefined && hex !== hoveredHex;
      c.set(hex);
      if (dim) c.multiplyScalar(0.15);
      body.setColorAt(i, c);
      c.set(hex).offsetHSL(0, 0, 0.07);
      if (dim) c.multiplyScalar(0.15);
      stud.setColorAt(i, c);
    }
    if (body.instanceColor) body.instanceColor.needsUpdate = true;
    if (stud.instanceColor) stud.instanceColor.needsUpdate = true;
  }, [hoveredHex]);

  useEffect(() => {
    if (controlsRef.current) controlsRef.current.autoRotate = autoRotate;
  }, [autoRotate]);

  return (
    <div className="relative w-full h-full">
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">
          Building 3D scene…
        </div>
      )}
      <div ref={mountRef} className="w-full h-full" />
      <div className="absolute bottom-3 right-3 flex gap-2">
        <button
          onClick={() => setAutoRotate(v => !v)}
          className="px-3 py-1.5 text-xs font-medium bg-slate-900/80 hover:bg-slate-800 text-slate-200 rounded-lg backdrop-blur-sm border border-slate-700 transition"
        >
          {autoRotate ? "Pause Rotation" : "Auto Rotate"}
        </button>
      </div>
      <p className="absolute bottom-3 left-3 text-[11px] text-slate-500 pointer-events-none">
        Drag to rotate · Scroll to zoom
      </p>
    </div>
  );
}
