CREATE TABLE fpg_p01_floor_plan_run (
	id INTEGER NOT NULL, 
	experiment_id INTEGER NOT NULL, 
	source_trial_id INTEGER, 
	status VARCHAR(32) NOT NULL, 
	source_candidate_data JSON, 
	circulation_data JSON, 
	generation_specification JSON, 
	initial_solver_data JSON, 
	refinement_a_data JSON, 
	refinement_b_data JSON, 
	post_processing_data JSON, 
	opening_generation_data JSON, 
	floor_plan_scoring_data JSON, 
	final_floor_plan JSON, 
	final_score FLOAT, 
	error_data JSON, 
	duration_ms INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	finished_at DATETIME, 
	CONSTRAINT pk_fpg_p01_floor_plan_run PRIMARY KEY (id), 
	CONSTRAINT fk_p01_run_source_trial_experiment FOREIGN KEY(source_trial_id, experiment_id) REFERENCES fpg_p01_candidate_trial (id, experiment_id) ON DELETE CASCADE, 
	CONSTRAINT uq_p01_run_source_trial UNIQUE (source_trial_id), 
	CONSTRAINT fk_fpg_p01_floor_plan_run_experiment_id_fpg_p01_experiment FOREIGN KEY(experiment_id) REFERENCES fpg_p01_experiment (id) ON DELETE CASCADE
);
CREATE INDEX ix_fpg_p01_floor_plan_run_experiment_id ON fpg_p01_floor_plan_run (experiment_id);
CREATE INDEX ix_fpg_p01_run_experiment_status ON fpg_p01_floor_plan_run (experiment_id, status);
