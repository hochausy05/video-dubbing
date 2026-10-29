from __future__ import annotations

import unittest
import uuid

from app.services.joint_timeline import (
    JointInputSegment,
    MeasuredAudioCandidate,
    build_joint_timeline_plan,
    seconds_to_us,
)


PROJECT = uuid.UUID("00000000-0000-0000-0000-000000000001")


def candidate(rate: int, duration_us: int, seed: int) -> MeasuredAudioCandidate:
    return MeasuredAudioCandidate(uuid.UUID(f"00000000-0000-0000-0000-{seed:012d}"), rate, duration_us)


class JointTimelineTests(unittest.TestCase):
    def plan(self, window_us: int, candidates: tuple[MeasuredAudioCandidate, ...], *, margin=0, precise=True):
        return build_joint_timeline_plan(
            project_id=PROJECT, project_revision=7, video_duration_us=window_us,
            segments=(JointInputSegment(
                uuid.UUID("00000000-0000-0000-0000-000000000010"), 0, 0, window_us, candidates,
            ),), coverage_precision_verified=precise, coverage_margin_us=margin,
        )

    def test_balances_measured_rate_and_video_speed_instead_of_max_rate(self):
        plan = self.plan(700_000, (
            candidate(0, 1_400_000, 1),
            candidate(25, 1_000_000, 2),
            candidate(35, 700_000, 3),
        ))
        chosen = plan.segments[0]
        self.assertTrue(plan.joint_feasible)
        self.assertEqual(chosen.rate_percent, 25)
        self.assertAlmostEqual(chosen.video_speed, 0.7)
        self.assertFalse(plan.renderable)
        self.assertFalse(plan.renderer_supported)

    def test_positive_slack_is_preserved_and_never_rounded_down(self):
        plan = self.plan(1_015_000, (candidate(0, 1_000_000, 4),))
        self.assertEqual(plan.segments[0].signed_slack_us, 15_000)
        self.assertEqual(seconds_to_us("1.0000001"), 1_000_001)

    def test_zero_slack_requires_verified_precision(self):
        verified = self.plan(1_000_000, (candidate(0, 1_000_000, 5),))
        unverified = self.plan(1_000_000, (candidate(0, 1_000_000, 6),), precise=False)
        self.assertTrue(verified.joint_feasible)
        self.assertEqual(verified.segments[0].signed_slack_us, 0)
        self.assertFalse(unverified.joint_feasible)

    def test_positive_margin_is_required_when_precision_is_unverified(self):
        plan = self.plan(1_050_000, (candidate(0, 1_000_000, 7),), margin=50_000, precise=False)
        self.assertTrue(plan.joint_feasible)
        self.assertEqual(plan.segments[0].signed_slack_us, 50_000)

    def test_already_synchronized_candidate_is_not_distorted(self):
        plan = self.plan(1_000_000, (candidate(0, 900_000, 12),))
        self.assertTrue(plan.joint_feasible)
        self.assertEqual(plan.segments[0].rate_percent, 0)
        self.assertEqual(plan.segments[0].video_speed, 1.0)
        self.assertEqual(plan.segments[0].signed_slack_us, 100_000)

    def test_candidate_rate_and_video_speed_limits_are_hard(self):
        with self.assertRaisesRegex(ValueError, "supported bounds"):
            self.plan(1_000_000, (candidate(36, 100_000, 13),))

    def test_global_mapping_is_continuous_and_covers_source_once(self):
        segments = (
            JointInputSegment(uuid.UUID("00000000-0000-0000-0000-000000000011"), 0, 100_000, 200_000,
                              (candidate(25, 200_000, 8),)),
            JointInputSegment(uuid.UUID("00000000-0000-0000-0000-000000000012"), 1, 400_000, 500_000,
                              (candidate(0, 100_000, 9),)),
        )
        plan = build_joint_timeline_plan(
            project_id=PROJECT, project_revision=0, video_duration_us=700_000,
            segments=segments, coverage_precision_verified=True, coverage_margin_us=0,
        )
        self.assertTrue(plan.joint_feasible)
        self.assertEqual(plan.video_intervals[0].source_start_us, 0)
        self.assertEqual(plan.video_intervals[-1].source_end_us, 700_000)
        for left, right in zip(plan.video_intervals, plan.video_intervals[1:]):
            self.assertEqual(left.source_end_us, right.source_start_us)
            self.assertEqual(left.output_end_us, right.output_start_us)
        self.assertEqual(sum(x.source_end_us - x.source_start_us for x in plan.video_intervals), 700_000)

    def test_overlapping_dialogue_with_slowdown_is_blocked(self):
        segments = (
            JointInputSegment(uuid.UUID("00000000-0000-0000-0000-000000000021"), 0, 0, 800_000,
                              (candidate(25, 800_000, 10),)),
            JointInputSegment(uuid.UUID("00000000-0000-0000-0000-000000000022"), 1, 500_000, 900_000,
                              (candidate(0, 100_000, 11),)),
        )
        plan = build_joint_timeline_plan(
            project_id=PROJECT, project_revision=0, video_duration_us=1_000_000,
            segments=segments, coverage_precision_verified=True, coverage_margin_us=0,
        )
        self.assertFalse(plan.joint_feasible)
        self.assertIn("joint_overlap_unsafe", {issue.code for issue in plan.blocking_issues})


if __name__ == "__main__":
    unittest.main()
