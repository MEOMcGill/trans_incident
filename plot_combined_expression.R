source("C:/Users/math_/.claude/skills/survey-search/scripts/survey_utils.R")
source("C:/Users/math_/Dropbox/PC/Documents/GitHub/ai_interns/templates/meo_theme.R")
library(dplyr)
library(tidyr)
library(lmtest)
library(sandwich)
library(stringr)

# ── 1. Load and prepare data ────────────────────────────────────────────────

catalogue <- load_catalogue()
data <- read.csv("C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/harmonized_data.csv",
                 fileEncoding = "UTF-8-BOM")
data <- clean_survey_data(data, catalogue)
data <- weight_survey_data(data, catalogue, method = "rake")

data <- data %>%
  mutate(
    # Comfort DVs: binary (at least somewhat comfortable = 0-4 scale, >=2)
    dv_comfort_online  = as.integer(as.numeric(pol_speech_1) >= 2),
    dv_comfort_respond = as.integer(as.numeric(pol_speech_2) >= 2),
    dv_comfort_work    = as.integer(as.numeric(pol_speech_3) >= 2),
    # Expression DVs: binary (did at least once in past month)
    dv_post            = as.integer(as.numeric(pol_behav_3) >= 1),
    dv_share           = as.integer(as.numeric(pol_behav_2) >= 1),
    dv_talk_online     = as.integer(as.numeric(pol_talk_3) >= 1),
    dv_talk_coworkers  = as.integer(as.numeric(pol_talk_2) >= 1),
    # Gender identity
    gender_identity = as.numeric(gender1),
    gender_group = case_when(
      gender_identity == 0 ~ "Man",
      gender_identity == 1 ~ "Woman",
      gender_identity %in% c(2, 3) ~ "Non-binary / Other",
      TRUE ~ NA_character_
    ),
    is_trans = case_when(
      as.numeric(gender2) == 1 ~ 1L,
      as.numeric(gender2) == 0 ~ 0L,
      TRUE ~ NA_integer_
    ),
    gender_minority = case_when(
      gender_group == "Non-binary / Other" | is_trans == 1 ~ 1L,
      gender_group %in% c("Man", "Woman") & (is_trans == 0 | is.na(is_trans)) ~ 0L,
      TRUE ~ NA_integer_
    ),
    province_num = as.numeric(province),
    region = case_when(
      province_num %in% c(4, 5, 7, 10) ~ "Atlantic",
      province_num == 11 ~ "Quebec",
      province_num == 9 ~ "Ontario",
      province_num == 2 ~ "British Columbia",
      province_num %in% c(1, 3, 12) ~ "Prairies",
      TRUE ~ NA_character_
    ),
    age_num = as.numeric(age),
    pol_interest = as.numeric(pol_intrst_1),
    educ_num = as.numeric(educ),
    wave = factor(survey_name)
  )

# SM daily use
sm_old <- c("socialUse_1","socialUse_2","socialUse_3","socialUse_4",
            "socialUse_5","socialUse_6","socialUse_8")
sm_new <- c("socmed_use_1","socmed_use_2","socmed_use_3","socmed_use_4",
            "socmed_use_5","socmed_use_6","socmed_use_9")
sm_old <- sm_old[sm_old %in% names(data)]
sm_new <- sm_new[sm_new %in% names(data)]

data <- data %>%
  rowwise() %>%
  mutate(
    sm_old_daily = {
      vals <- suppressWarnings(as.numeric(c_across(all_of(sm_old))))
      if (all(is.na(vals))) NA_integer_ else as.integer(max(vals, na.rm = TRUE) >= 5)
    },
    sm_new_daily = {
      vals <- suppressWarnings(as.numeric(c_across(all_of(sm_new))))
      if (all(is.na(vals))) NA_integer_ else as.integer(max(vals, na.rm = TRUE) >= 3)
    }
  ) %>%
  ungroup() %>%
  mutate(sm_daily = coalesce(sm_old_daily, sm_new_daily))

# Analysis sample
analysis <- data %>%
  filter(!is.na(gender_minority), !is.na(age_num), !is.na(region),
         !is.na(pol_interest), !is.na(sm_daily), !is.na(educ_num))
cat("Analysis N:", nrow(analysis), "\n")
cat("Gender minority:", sum(analysis$gender_minority == 1), "\n")
cat("Cisgender:", sum(analysis$gender_minority == 0), "\n")

# ── 2. Fit models and compute predicted probabilities ────────────────────────

dv_info <- list(
  # Panel A: Comfort (% at least somewhat comfortable)
  list(var = "dv_comfort_online",  label = "Expressing opinions online",      panel = "Comfort with political expression"),
  list(var = "dv_comfort_respond", label = "Responding to disagreeable posts", panel = "Comfort with political expression"),
  list(var = "dv_comfort_work",    label = "Discussing politics at work/school", panel = "Comfort with political expression"),
  # Panel B: Expression (% who did at least once)
  list(var = "dv_post",            label = "Posted own political views on SM",      panel = "Political expression"),
  list(var = "dv_share",           label = "Shared political news on SM",           panel = "Political expression"),
  list(var = "dv_talk_online",     label = "Discussed politics with people online", panel = "Political expression"),
  list(var = "dv_talk_coworkers",  label = "Discussed politics with coworkers",     panel = "Political expression")
)

results <- list()

for (d in dv_info) {
  dv <- d$var
  label <- d$label
  panel <- d$panel

  df_model <- analysis %>% filter(!is.na(.data[[dv]]))

  f <- as.formula(paste(dv, "~ gender_minority + age_num + pol_interest + sm_daily +
                         educ_num + factor(region) + factor(wave)"))
  m <- lm(f, data = df_model, weights = wt)
  vcov_cl <- vcovCL(m, cluster = df_model$wave)

  for (gm in c(0, 1)) {
    newdata <- df_model
    newdata$gender_minority <- gm
    preds <- predict(m, newdata = newdata)
    avg_pred <- weighted.mean(preds, df_model$wt)

    set.seed(42)
    coef_draws <- MASS::mvrnorm(1000, coef(m), vcov_cl)
    X <- model.matrix(f, data = newdata)
    pred_draws <- X %*% t(coef_draws)
    avg_draws <- apply(pred_draws, 2, function(p) weighted.mean(p, df_model$wt))
    se_pred <- sd(avg_draws)

    results[[length(results) + 1]] <- data.frame(
      panel = panel,
      dv = label,
      group = ifelse(gm == 1, "Non-binary/Trans", "Cisgender"),
      pct = avg_pred * 100,
      lo = (avg_pred - 1.96 * se_pred) * 100,
      hi = (avg_pred + 1.96 * se_pred) * 100,
      stringsAsFactors = FALSE
    )
  }
}

res <- bind_rows(results)

res$group <- factor(res$group, levels = c("Non-binary/Trans", "Cisgender"))
res$panel <- factor(res$panel, levels = c("Comfort with political expression", "Political expression"))
res$dv <- factor(res$dv, levels = c(
  "Expressing opinions online",
  "Responding to disagreeable posts",
  "Discussing politics at work/school",
  "Posted own political views on SM",
  "Shared political news on SM",
  "Discussed politics with people online",
  "Discussed politics with coworkers"
))

cat("\nPredicted probabilities:\n")
print(res %>% select(panel, dv, group, pct, lo, hi) %>% mutate(across(pct:hi, ~round(., 1))))

# ── 3. Plot ──────────────────────────────────────────────────────────────────

# Create short labels for the legend, unique per panel
res$dv_short <- case_when(
  res$dv == "Expressing opinions online"           ~ "Express opinions online",
  res$dv == "Responding to disagreeable posts"      ~ "Respond to disagreeable posts",
  res$dv == "Discussing politics at work/school"    ~ "Discuss politics at work/school",
  res$dv == "Posted own political views on SM"      ~ "Post own views on SM",
  res$dv == "Shared political news on SM"           ~ "Share political news on SM",
  res$dv == "Discussed politics with people online" ~ "Discuss politics online",
  res$dv == "Discussed politics with coworkers"     ~ "Discuss politics with coworkers"
)

# Separate plots for each panel to avoid legend confusion
res_comfort <- res %>% filter(panel == "Comfort with political expression")
res_express <- res %>% filter(panel == "Political expression")

p_comfort <- ggplot(res_comfort, aes(x = pct, y = group, color = dv_short)) +
  geom_pointrange(aes(xmin = lo, xmax = hi),
    size = 0.5, linewidth = 0.7,
    position = position_dodge(width = 0.7)) +
  geom_text(aes(label = paste0(round(pct), "%")),
    vjust = -1.3, size = 2.8, family = "poppins", show.legend = FALSE,
    position = position_dodge(width = 0.7)) +
  scale_x_continuous(limits = c(0, 80), breaks = seq(0, 80, 20),
                     labels = paste0(seq(0, 80, 20), "%")) +
  scale_color_manual(values = c(
    "Express opinions online"           = "#1A4AAD",
    "Respond to disagreeable posts"     = "#D71B1E",
    "Discuss politics at work/school"   = "#229A44"
  )) +
  labs(title = "Comfort with political expression",
       subtitle = "% who feel at least somewhat comfortable",
       x = NULL, y = NULL, color = NULL) +
  theme_meo +
  theme(
    panel.grid.major.y = element_blank(),
    plot.title = element_text(size = 11, face = "bold"),
    plot.subtitle = element_text(size = 9),
    legend.position = "bottom",
    legend.text = element_text(size = 7.5)
  ) +
  guides(color = guide_legend(nrow = 1))

p_express <- ggplot(res_express, aes(x = pct, y = group, color = dv_short)) +
  geom_pointrange(aes(xmin = lo, xmax = hi),
    size = 0.5, linewidth = 0.7,
    position = position_dodge(width = 0.7)) +
  geom_text(aes(label = paste0(round(pct), "%")),
    vjust = -1.3, size = 2.8, family = "poppins", show.legend = FALSE,
    position = position_dodge(width = 0.7)) +
  scale_x_continuous(limits = c(0, 80), breaks = seq(0, 80, 20),
                     labels = paste0(seq(0, 80, 20), "%")) +
  scale_color_manual(values = c(
    "Post own views on SM"              = "#1A4AAD",
    "Share political news on SM"        = "#D71B1E",
    "Discuss politics online"           = "#229A44",
    "Discuss politics with coworkers"   = "#FF8200"
  )) +
  labs(title = "Political expression",
       subtitle = "% who did each at least once in the past month",
       x = NULL, y = NULL, color = NULL) +
  theme_meo +
  theme(
    panel.grid.major.y = element_blank(),
    plot.title = element_text(size = 11, face = "bold"),
    plot.subtitle = element_text(size = 9),
    legend.position = "bottom",
    legend.text = element_text(size = 7.5)
  ) +
  guides(color = guide_legend(nrow = 1))

# Combine with patchwork
library(patchwork)

p <- p_comfort / p_express +
  plot_annotation(
    caption = str_wrap(paste0(
      "Political expression by gender identity. ",
      "Predicted % from OLS controlling for age, political interest, daily SM use, education, region, and survey wave. ",
      "MEO | 17 tracking surveys, Jul 2024 \u2013 Feb 2026 | ",
      "Cisgender N = ", format(sum(analysis$gender_minority == 0), big.mark = ","),
      ", Non-binary/Trans N = ", format(sum(analysis$gender_minority == 1), big.mark = ","),
      " | Average predictions at observed covariate values | Wave-clustered SEs via simulation"
    ), width = 100),
    theme = theme_meo
  )

save_plot(p, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/figures/combined_expression",
          width = 8, height = 9)
cat("\nPlot saved.\n")
