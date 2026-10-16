ata_type == "reviews":
            if "is_llm_sample" in df.columns:
                llm_cnt = df["is_llm_sample"].sum()
                llm_status = "PASS" if llm_cnt == SAMPLES["llm_samples"] else "FAIL"
                print(f"[{llm_status}] Review LLM Sample: {llm_cnt} / {SAMPLES['llm_samples']}")
            else:
                print(f"[FAIL] Thiếu cột 'is_llm_sample'")

            if "is_manual_sample" in df.columns:
                manual_cnt = df["is_manual_sample"].sum()
                manual_status = "PASS" if manual_cnt == SAMPLES["manual_samples"] else "FAIL"
                print(f"[{manual_status}] Review Nhãn tay Sample: {manual_cnt} / {SAMPLES['manual_samples']}")
            else:
                print(f"[FAIL] Thiếu cột 'is_manual_sample'")