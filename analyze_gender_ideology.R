library(dplyr)
library(tidyr)

# Load data
df <- read.csv("C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/harmonized_data.csv")

# Clean: keep finished only
df <- df %>% filter(Finished == 1)
cat("N after cleaning:", nrow(df), "\n\n")

# Load pre-computed weights
wt_path <- "C:/Users/math_/.claude/skills/survey-search/data/weights.csv"
if (file.exists(wt_path)) {
  wts <- read.csv(wt_path)
  wts_sub <- wts %>% filter(survey_name == "2025_10_Tracking") %>% select(ResponseId, wt_rake)
  df <- df %>% left_join(wts_sub, by = "ResponseId")
  df$wt <- ifelse(is.na(df$wt_rake), 1, df$wt_rake)
  cat("Weight coverage:", round(mean(!is.na(df$wt_rake))*100,1), "%\n")
  cat("Weight stats: mean=", round(mean(df$wt),3), " sd=", round(sd(df$wt),3),
      " range=[", round(min(df$wt),3), ",", round(max(df$wt),3), "]\n\n")
} else {
  df$wt <- 1
  cat("No weight file found, using unweighted\n\n")
}

# DV: claims_believe_8 (1=Def false, 2=Prob false, 3=Not sure, 4=Prob true, 5=Def true)
df$believe <- factor(df$claims_believe_8, levels=1:5,
                     labels=c("Definitely false","Probably false","Not sure","Probably true","Definitely true"))

# Heard (0=No, 1=Yes in the data)
df$heard <- factor(df$claims_heard_8, levels=c(1,0), labels=c("Yes","No"))

# Age groups
df$age_group <- cut(df$age, breaks=c(0,29,44,59,100), labels=c("18-29","30-44","45-59","60+"))

# Gender (0=Man, 1=Woman, 2=Non-binary, 3=Other, 99=Prefer not to say)
df$gender_label <- case_when(
  df$gender1 == 0 ~ "Man",
  df$gender1 == 1 ~ "Woman",
  df$gender1 %in% c(2,3) ~ "Non-binary/Other",
  TRUE ~ NA_character_
)

# Ideology (0-10 scale, 0=left, 10=right)
df$ideo_group <- cut(df$ideology_1, breaks=c(-1,3,6,10), labels=c("Left (0-3)","Centre (4-6)","Right (7-10)"))

# Party
df$party_label <- case_when(
  df$party == 1 ~ "Conservative",
  df$party == 2 ~ "Liberal",
  df$party == 3 ~ "NDP",
  df$party == 4 ~ "Bloc Québécois",
  df$party == 5 ~ "Green",
  df$party == 6 ~ "PPC",
  df$party == 8 ~ "No party",
  TRUE ~ NA_character_
)

# Political posting: pol_behav_3 (0=Never, 1-6=increasing frequency)
df$posts_politics <- case_when(
  df$pol_behav_3 == 0 ~ "Never",
  df$pol_behav_3 %in% c(1,2) ~ "Occasionally",
  df$pol_behav_3 %in% c(3,4,5,6) ~ "Frequently",
  TRUE ~ NA_character_
)

# Comfort expressing political opinions online: pol_speech_1
# 0=Not at all, 1=Not very, 2=Somewhat, 3=Comfortable, 4=Very comfortable
df$comfort_express <- case_when(
  df$pol_speech_1 %in% c(0,1) ~ "Not comfortable",
  df$pol_speech_1 == 2 ~ "Somewhat",
  df$pol_speech_1 %in% c(3,4) ~ "Comfortable",
  TRUE ~ NA_character_
)

# Comfort responding to disagreeable posts: pol_speech_2
df$comfort_respond <- case_when(
  df$pol_speech_2 %in% c(0,1) ~ "Not comfortable",
  df$pol_speech_2 == 2 ~ "Somewhat",
  df$pol_speech_2 %in% c(3,4) ~ "Comfortable",
  TRUE ~ NA_character_
)

# ---- ANALYSIS ----

# Helper: weighted crosstab
wtab <- function(data, group_var) {
  data %>%
    filter(!is.na(.data[[group_var]]), !is.na(believe)) %>%
    group_by(.data[[group_var]], believe) %>%
    summarise(n_wt = sum(wt), .groups="drop") %>%
    group_by(.data[[group_var]]) %>%
    mutate(pct = round(n_wt/sum(n_wt)*100, 1),
           N = round(sum(n_wt))) %>%
    ungroup()
}

cat("=== OVERALL DISTRIBUTION (weighted) ===\n")
overall <- df %>% filter(!is.na(believe)) %>%
  group_by(believe) %>% summarise(n_wt=sum(wt)) %>%
  mutate(pct=round(n_wt/sum(n_wt)*100,1))
print(as.data.frame(overall))
cat("\nN (rated belief, unweighted):", sum(!is.na(df$believe)), "\n")
cat("% who heard of claim (weighted):",
    round(sum(df$wt[df$claims_heard_8==1 & !is.na(df$claims_heard_8)]) /
          sum(df$wt[!is.na(df$claims_heard_8)])*100, 1), "%\n\n")

cat("=== BY AGE GROUP ===\n")
t1 <- wtab(df, "age_group")
print(as.data.frame(t1 %>% select(age_group, believe, pct, N) %>%
  pivot_wider(names_from=believe, values_from=pct, values_fill=0)))

cat("\n=== BY GENDER ===\n")
t2 <- wtab(df, "gender_label")
print(as.data.frame(t2 %>% select(gender_label, believe, pct, N) %>%
  pivot_wider(names_from=believe, values_from=pct, values_fill=0)))

cat("\n=== BY IDEOLOGY ===\n")
t3 <- wtab(df, "ideo_group")
print(as.data.frame(t3 %>% select(ideo_group, believe, pct, N) %>%
  pivot_wider(names_from=believe, values_from=pct, values_fill=0)))

cat("\n=== BY PARTY ===\n")
t4 <- wtab(df, "party_label")
print(as.data.frame(t4 %>% select(party_label, believe, pct, N) %>%
  pivot_wider(names_from=believe, values_from=pct, values_fill=0)))

cat("\n=== BY POLITICAL POSTING FREQUENCY ===\n")
t5 <- wtab(df, "posts_politics")
print(as.data.frame(t5 %>% select(posts_politics, believe, pct, N) %>%
  pivot_wider(names_from=believe, values_from=pct, values_fill=0)))

cat("\n=== BY COMFORT EXPRESSING POLITICAL OPINIONS ONLINE ===\n")
t6 <- wtab(df, "comfort_express")
print(as.data.frame(t6 %>% select(comfort_express, believe, pct, N) %>%
  pivot_wider(names_from=believe, values_from=pct, values_fill=0)))

cat("\n=== BY COMFORT RESPONDING TO DISAGREEABLE POSTS ===\n")
t7 <- wtab(df, "comfort_respond")
print(as.data.frame(t7 %>% select(comfort_respond, believe, pct, N) %>%
  pivot_wider(names_from=believe, values_from=pct, values_fill=0)))

# Save cleaned + weighted data (separate file to avoid overwriting extract)
write.csv(df, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/harmonized_data_weighted.csv", row.names=FALSE)
cat("\nData saved to harmonized_data_weighted.csv\n")
