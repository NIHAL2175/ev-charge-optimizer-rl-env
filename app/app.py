import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import random
import numpy as np
import torch
import uvicorn
import threading
from fastapi import FastAPI
from stable_baselines3 import PPO
from gymnasium.wrappers import FlattenObservation
from env.ev_env import EVChargingEnv, grade_agent
from ui import create_gradio_app  # type: ignore

app = FastAPI(title="EV Charging RL Optimization API")

def run_episode(env, model=None, is_rl_fallback=False, log_steps=False):
    obs, info = env.reset()
    step = 0
    while True:
        if model is not None:
            action, _ = model.predict(obs, deterministic=True)
        else:
            if is_rl_fallback:
                action = np.zeros(env.unwrapped.num_chargers, dtype=np.float32)
                current_time = env.unwrapped.current_step
                target_soc = env.unwrapped.config["TARGET_SOC"]
                for i in range(env.unwrapped.num_chargers):
                    soc = env.unwrapped.soc[i]
                    remaining = env.unwrapped.departure_times[i] - current_time
                    if soc < target_soc:
                        if remaining < 5:
                            action[i] = 1.0
                        elif current_time < 8 or current_time > 20:
                            action[i] = 0.7
                        else:
                            action[i] = 0.3
            else:
                action = np.ones(env.unwrapped.num_chargers, dtype=np.float32) * 0.5
            
        obs, reward, terminated, truncated, info = env.step(action)
        step += 1
        done = terminated or truncated
            
        if done:
            break
    
    return {
        "cost": float(env.unwrapped.total_cost),
        "soc": float(np.mean(env.unwrapped.soc)),
        "penalty": float(env.unwrapped.total_overload_penalty)
    }, step

@app.get("/")
def health_check() -> dict:
    return {"status": "active", "message": "EV Charging Environment API is running"}

@app.get("/run")
def run_inference(difficulty: str = "medium", seed: int = 42) -> dict:
    """Run simulated episodes with deterministic seeding"""
    print("[START] task=" + difficulty + " env=EVChargingEnv model=api", flush=True)
    try:
        if difficulty not in ["easy", "medium", "hard"]:
            return {"error": "Invalid difficulty. Choose easy, medium, or hard."}
            
        env = FlattenObservation(EVChargingEnv(difficulty=difficulty))
        env.reset(seed=seed)
        
        use_model = False
        model = None
        if os.path.exists("models/ev_charging_ppo_robust") or os.path.exists("models/ev_charging_ppo_robust.zip"):
            model = PPO.load("models/ev_charging_ppo_robust")
            use_model = True
            
        np.random.seed(seed)
        random.seed(seed)
        torch.manual_seed(seed)
        
        baseline_res, _ = run_episode(env, model=None, is_rl_fallback=False, log_steps=False)
        baseline = baseline_res
        
        env = FlattenObservation(EVChargingEnv(difficulty=difficulty))
        env.reset(seed=seed)
        
        rl_res, rl_steps = run_episode(env, model=model, is_rl_fallback=not use_model, log_steps=True)
        rl = rl_res

        baseline_score = float(grade_agent(
            baseline["cost"],
            baseline["soc"],
            baseline["penalty"]
        ))

        rl_score = float(grade_agent(
            rl["cost"],
            rl["soc"],
            rl["penalty"]
        ))

        baseline_score = round(float(max(0.0, min(1.0, baseline_score))), 4)
        rl_score = round(float(max(0.0, min(1.0, rl_score))), 4)

        baseline_cost = round(float(baseline["cost"]), 2)
        rl_cost = round(float(rl["cost"]), 2)
        
        baseline["cost"] = baseline_cost
        rl["cost"] = rl_cost
        
        baseline["soc"] = round(float(baseline["soc"]), 4)
        rl["soc"] = round(float(rl["soc"]), 4)
        
        baseline["penalty"] = round(float(baseline["penalty"]), 4)
        rl["penalty"] = round(float(rl["penalty"]), 4)

        if baseline_cost > 0.0:
            improvement_percent = f"{((baseline_cost - rl_cost) / baseline_cost) * 100.0:.2f}%"
        else:
            improvement_percent = "0.00%"

        print(f"[END] success=true steps={rl_steps} score={rl_score:.4f}", flush=True)

        return {
            "difficulty": difficulty,
            "baseline": baseline,
            "baseline_score": baseline_score,
            "rl": rl,
            "rl_score": rl_score,
            "improvement_percent": improvement_percent
        }
    except Exception:
        return {
            "difficulty": difficulty,
            "baseline": {"cost": 0.0, "soc": 0.0, "penalty": 0.0},
            "baseline_score": 0.0,
            "rl": {"cost": 0.0, "soc": 0.0, "penalty": 0.0},
            "rl_score": 0.0,
            "improvement_percent": "0.00%"
        }

@app.post("/reset")
def reset_env():
    try:
        env = EVChargingEnv()
        obs, _ = env.reset()
        return {"status": "ok"}
    except Exception:
        return {"status": "error"}

if __name__ == "__main__":
    env = EVChargingEnv()
    env_lock = threading.Lock()
    demo = create_gradio_app(env, env_lock)
    
    print("\n" + "="*50)
    print("Open this in your browser : http://127.0.0.1:7861")
    print("API is available at : http://127.0.0.1:8000")
    print("Uvicorn running at : http://127.0.0.1:8000/docs")
    print("="*50 + "\n")
    
    demo.launch(server_name="127.0.0.1", server_port=7861, prevent_thread_lock=True, quiet=True)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")
