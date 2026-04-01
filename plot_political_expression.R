source("C:/Users/math_/Dropbox/PC/Documents/GitHub/ai_interns/templates/meo_theme.R")
library(dplyr)
library(tidyr)
library(survey)
library(stringr)

# Load data (17 surveys)
df <- read.csv("C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/harmonized_data.csv")
df <- df %>% filter(Finished == 1)

# Weights
wt_path <- "C:/Users/math_/.claude/skills/survey-search/data/weights.csv"
wts <- read.csv(wt_path)
wts_sub <- wts %>% select(survey_name, ResponseId, wt_rake)
df <- df %>% left_join(wts_sub, by = c("survey_name", "ResponseId"))
df$wt <- ifelse(is.na(df$wt_rake), 1, df$wt_rake)
cat("N:", nrow(df), "\n")
cat("Weight coverage:", round(mean(!is.na(df$wt_rake)) * 100, 1), "%\n")

# --- Three DVs ---
# pol_behav_3: posted own political views on SM (0=Never, 1+=did it)
df$dv_post <- as.numeric(df$pol_behav_3 >= 1)
# pol_speech_2: comfort responding to disagreeable posts (0-4; >=2 = at least somewhat)
df$dv_respond <- as.numeric(df$pol_speech_2 >= 2)
# pol_speech_3: comfort expressing opinions at work/school (0-4; >=2 = at least somewhat)
df$dv_work <- as.numeric(df$pol_speech_3 >= 2)

# --- Gender identity ---
df$gender_id <- case_when(
  (df$gender1 %in% c(0, 1)) & (df$gender2 != 1 | is.na(df$gender2)) ~ "Cisgender",
  (df$gender1 %in% c(2, 3)) | (df$gender2 == 1) ~ "Non-binary/Trans",
  TRUE ~ NA_character_
)

cat("Cisgender:", sum(df$gender_id == "Cisgender", na.rm = TRUE), "\n")
cat("Non-binary/Trans:", sum(df$gender_id == "Non-binary/Trans", na.rm = TRUE), "\n")

# --- Compute weighted % with CIs ---
compute_ci <- function(data, group_var, dv_var, dv_label) {
  data <- data %>% filter(!is.na(.data[[group_var]]), !is.na(.data[[dv_var]]))
  if (nrow(data) < 10) return(NULL)
  des <- svydesign(ids = ~1, weights = ~wt, data = data)

  results <- data %>%
    distinct(.data[[group_var]]) %>%
    pull(1) %>%
    lapply(function(level) {
      sub <- subset(des, data[[group_var]] == level)
      n_sub <- sum(data[[group_var]] == level, na.rm = TRUE)
      if (n_sub < 10) return(NULL)
      formula <- as.formula(paste0("~", dv_var))
      m <- svymean(formula, sub)
      ci <- confint(m)
      data.frame(
        category = as.character(level),
        pct = as.numeric(m) * 100,
        lo = ci[1] * 100,
        hi = ci[2] * 100,
        n = n_sub,
        dv = dv_label,
        stringsAsFactors = FALSE
      )
    }) %>% bind_rows()

  results
}

dvs <- list(
  list("dv_post", "Posts political views online"),
  list("dv_respond", "Responds to disagreeable posts"),
  list("dv_work", "Discusses politics at work/school")
)

res <- bind_rows(lapply(dvs, function(d) {
  compute_ci(df, "gender_id", d[[1]], d[[2]])
}))

res$category <- factor(res$category, levels = c("Non-binary/Trans", "Cisgender"))

res$dv <- factor(res$dv, levels = c(
  "Posts political views online",
  "Responds to disagreeable posts",
  "Discusses politics at work/school"
))

# Plot
p <- ggplot(res, aes(x = pct, y = category, color = dv)) +
  geom_pointrange(aes(xmin = lo, xmax = hi),
    size = 0.5, linewidth = 0.7,
    position = position_dodge(width = 0.6)) +
  geom_text(aes(label = paste0(round(pct), "%")),
    vjust = -1.3, size = 3, family = "poppins", show.legend = FALSE,
    position = position_dodge(width = 0.6)) +
  scale_x_continuous(limits = c(0, 80), breaks = seq(0, 80, 20),
                     labels = paste0(seq(0, 80, 20), "%")) +
  scale_color_manual(values = c(
    "Posts political views online" = "#1A4AAD",
    "Responds to disagreeable posts" = "#D71B1E",
    "Discusses politics at work/school" = "#229A44"
  )) +
  labs(
    title = "Political expression by gender identity",
    subtitle = str_wrap("% who post views (past month) | are at least somewhat comfortable responding/discussing", width = 70),
    x = NULL, y = NULL,
    caption = paste0("MEO Lab | 17 tracking surveys, Jul 2024 \u2013 Feb 2026 | ",
                     "Cisgender N = ", format(sum(res$n[res$category == "Cisgender"]) / 3, big.mark = ","),
                     ", Non-binary/Trans N = ", format(sum(res$n[res$category == "Non-binary/Trans"]) / 3, big.mark = ","),
                     " | Weighted with 95% CIs")
  ) +
  theme_meo +
  theme(
    panel.grid.major.y = element_blank(),
    plot.title = element_text(size = 12),
    legend.position = "bottom",
    legend.text = element_text(size = 8)
  ) +
  guides(color = guide_legend(nrow = 1))

save_plot(p, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/figures/political_expression",
          width = 7.5, height = 4)
cat("Plot saved.\n")
