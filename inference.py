import sys
import os
import json
import numpy as np
from env.ev_env import EVChargingEnv, grade_agent
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def log_start(task, env, model):
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step, action, reward, done, error):
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(f"[STEP] step={step} action={action} reward={reward:.4f} done={done_val} error={error_val}", flush=True)

def log_end(success, steps, score, rewards):
    rewards_str = ",".join(f"{r:.4f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.4f} rewards={rewards_str}", flush=True)

def main():
    USE_OPENAI = os.getenv("USE_OPENAI", "True").lower() in ("true", "1", "yes")
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
    
    API_KEY = os.getenv("OPENAI_API_KEY")
    HF_TOKEN = os.getenv("HF_TOKEN")
    active_key = HF_TOKEN if HF_TOKEN else API_KEY
    
    API_BASE_URL = os.getenv("API_BASE_URL")
    
    api_active = USE_OPENAI and bool(active_key)
    if api_active:
        print("Running with OpenAI API", flush=True)
    else:
        print("Running in fallback mode (no API)", flush=True)
        
    if api_active:
        if not API_BASE_URL and active_key and active_key.startswith("sk-or-"):
            API_BASE_URL = "https://openrouter.ai/api/v1"
            
        if API_BASE_URL:
            client = OpenAI(base_url=API_BASE_URL, api_key=active_key)
        else:
            client = OpenAI(api_key=active_key)
    else:
        client = None

    difficulties = ["easy", "medium", "hard"]

    for difficulty in difficulties:
        log_start(task=difficulty, env="EVChargingEnv", model=MODEL_NAME)

        success = False
        steps = 0
        score = 0.0
        rewards = []
        
        try:
            env = EVChargingEnv(difficulty=difficulty)
            obs, _ = env.reset(seed=42)
            
            for step in range(1, env.max_ep_steps + 1):
                action_arr = None
                
                if api_active:
                    obs_serializable = {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in obs.items()}
                    prompt = (
                        "You are an AI optimizing EV charging. Given the environment observation, "
                        "output exactly a JSON object with a single key 'action' that maps to a list of "
                        f"{env.num_chargers} floats (between 0.0 and 1.0) representing the charging rate for each vehicle.\n"
                        f"Observation: {json.dumps(obs_serializable)}\n"
                        "Example response: {\"action\": [0.5, 0.0, 1.0, 0.2, 0.8]}"
                    )
                    
                    try:
                        response = client.chat.completions.create(
                            model=MODEL_NAME,
                            messages=[{"role": "user", "content": prompt}],
                            response_format={"type": "json_object"},
                            temperature=0.1
                        )
                        content = response.choices[0].message.content.strip()
                        parsed = json.loads(content)
                        
                        if "action" in parsed and isinstance(parsed["action"], list):
                            action_arr = np.array(parsed["action"], dtype=np.float32)
                    except Exception as api_err:
                        print(f"[WARN] API Error at step {step}: {api_err}", flush=True)
                        print("Switching to fallback mode (no API)", flush=True)
                        api_active = False
                        
                if not api_active or action_arr is None or len(action_arr) != env.num_chargers:
                    target_soc = env.config["TARGET_SOC"]
                    action_list = []
                    for i in range(env.num_chargers):
                        current_soc = float(obs["soc"][i])
                        action_list.append(min(1.0, max(0.0, target_soc - current_soc)))
                    action_arr = np.array(action_list, dtype=np.float32)
                
                action_arr = np.clip(action_arr, 0.0, 1.0)
                
                obs, reward, done, info = env.openenv_step(action_arr)
                
                rewards.append(reward)
                log_step(step, action_arr.tolist(), reward, done, None)
                
                steps += 1
                
                if done:
                    score = grade_agent(info["total_cost"], info["mean_soc"], info["total_overload_penalty"])
                    success = score > 0.1
                    break
                    
        except Exception as e:
            error_msg = str(e).replace('\n', ' ')
            log_step(1, "error", 0.0, True, error_msg)
            steps = 1
            success = False
            
        log_end(success, steps, score, rewards)

if __name__ == "__main__":
    main()
